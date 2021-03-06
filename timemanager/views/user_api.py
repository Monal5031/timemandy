from flask_restplus import Namespace, Resource, fields
from flask_login import login_required
from flask import g

from timemanager.models.user_model import User as UserModel  # noqa

from timemanager.helpers.dao import BaseDAO
from timemanager.helpers.database import save_to_db
from timemanager.helpers.auth import hash_password, login_optional
from timemanager.helpers.errors import ValidationError
from timemanager.helpers.utils import AUTH_HEADER_DEFN
from timemanager.helpers.permissions import has_user_access, staff_only


api = Namespace('users', description='Users', path='/')  # noqa

USER = api.model('User', {
    'id': fields.Integer(required=True),
    'email': fields.String(required=True),
    'username': fields.String(required=True),
    'pref_wh': fields.Float(),
    'full_name': fields.String(),
    'is_admin': fields.Boolean(default=False),
    'is_manager': fields.Boolean(default=False),
})

USER_POST = api.clone('UserPost', USER, {
    'password': fields.String(required=True),
})
del USER_POST['id']

USER_PUT = api.clone('UserPut', USER_POST)


class UserDAO(BaseDAO):
    def create(self, data):
        # validate
        data = self.validate(data)
        # set password
        data = self.update_password(data)
        # save to database
        user = self.model(**data)
        if not save_to_db(user):
            raise ValidationError('email', 'The username or email already exists')
        # return token at login
        return self.get(user.id), 201

    def update_password(self, data):
        phash, salt = hash_password(data['password'])
        del data['password']
        data['phash'] = phash
        data['salt'] = salt.decode('utf-8')
        return data

    def update(self, id_, data):
        # validate
        data = self.validate(data, check_required=False)
        # update password
        if data.get('password'):
            data = self.update_password(data)
        # save
        return super(UserDAO, self).update(id_, data, validate=False, user_id=None)

    def fix_access_levels(self, data, id_=None):
        """
        fixes is_admin and is_manager levels
        """
        current_user = g.current_user
        # solve
        if current_user and current_user.is_admin:  # all is good
            return data
        if current_user and current_user.is_manager:  # can change own power, not anyone else
            data['is_admin'] = False  # don't allow to make anyone admin
            if current_user.id != id_:
                data['is_manager'] = False  # this happens in new user case
            return data
        # normal user case
        data['is_admin'] = False
        data['is_manager'] = False
        return data




DAO = UserDAO(UserModel, USER_POST, USER_PUT)


@api.route('/users/<int:user_id>')
class User(Resource):
    @login_required
    @has_user_access
    @api.header(*AUTH_HEADER_DEFN)
    @api.doc('get_user')
    @api.marshal_with(USER)
    def get(self, user_id):
        """Fetch a user given its id"""
        return DAO.get(user_id)

    @login_required
    @has_user_access
    @api.header(*AUTH_HEADER_DEFN)
    @api.doc('update_user')
    @api.marshal_with(USER)
    @api.expect(USER_PUT)
    def put(self, user_id):
        """Update a user given its id"""
        # fix access level
        data = DAO.fix_access_levels(self.api.payload, id_=user_id)
        return DAO.update(user_id, data)

    @login_required
    @has_user_access
    @api.header(*AUTH_HEADER_DEFN)
    @api.doc('delete_user')
    @api.marshal_with(USER)
    def delete(self, user_id):
        """Delete a user given its id"""
        return DAO.delete(user_id, user_id=None)


@api.header(*AUTH_HEADER_DEFN)
@api.route('/users/user')
class UserCurrent(Resource):
    @login_required
    @api.doc('get_user_current')
    @api.marshal_with(USER)
    def get(self):
        """Fetch the current user"""
        return DAO.get(g.current_user.id)


@api.route('/users')
class UserList(Resource):
    @api.header(*AUTH_HEADER_DEFN)
    @login_optional
    @api.doc('create_user')
    @api.marshal_with(USER)
    @api.expect(USER_POST)
    def post(self):
        """Create an user"""
        # fix access level
        data = DAO.fix_access_levels(self.api.payload)
        return DAO.create(data)

    @api.header(*AUTH_HEADER_DEFN)
    @login_required
    @staff_only
    @api.doc('list_users')
    @api.marshal_list_with(USER)
    def get(self):
        """List all users"""
        user = g.current_user
        if user.is_admin:
            return DAO.list()
        else:
            return DAO.list(**{'is_admin': False, 'is_manager': False})
