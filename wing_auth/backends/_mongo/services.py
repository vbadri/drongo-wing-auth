from .models import User, UserToken

from datetime import datetime
from passlib.hash import pbkdf2_sha256

import uuid


HASHER = pbkdf2_sha256.using(rounds=10000)


class UserServiceBase(object):
    @classmethod
    def init(cls, module):
        cls.module = module
        User.set_collection(
            module.database.instance.get_collection('auth_users')
        )

        UserToken.set_collection(
            module.database.instance.get_collection('auth_user_tokens')
        )


class UserForTokenService(UserServiceBase):
    def __init__(self, token):
        self.token = token

    def call(self):
        token = UserToken.objects.find_one(token=self.token)

        if token is None:
            return None

        if token.expires < datetime.utcnow():
            token.delete()
            return None

        token.refresh()
        return token.user


class UserCreateService(UserServiceBase):
    def __init__(self, username, password, active=False, superuser=False):
        self.username = username
        self.password = HASHER.hash(password)
        self.active = active
        self.superuser = superuser

    def call(self, ctx=None):
        if User.objects.find_one(username=self.username) is not None:
            raise Exception('User already exists.')

        return User.create(
            username=self.username,
            password=self.password,
            active=self.active,
            superuser=self.superuser,
            created_on=datetime.utcnow()
        )


class UserLoginService(UserServiceBase):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def check_credentials(self):
        user = User.objects.find_one(username=self.username, active=True)
        if user is None:
            return False

        return HASHER.verify(self.password, user.password)

    def create_token(self):
        user = User.objects.find_one(username=self.username, active=True)
        token = UserToken.create(
            user=user,
            token=uuid.uuid4().hex
        )
        token.refresh()
        return token.token

    def authenticate_session(self, ctx):
        sess = ctx.modules.session.get(ctx)
        user = User.objects.find_one(username=self.username, active=True)

        sess.user = {
            'is_authenticated': True,
            'is_superuser': user.superuser,
            'username': user.username
        }

    def call(self, ctx):
        sess = ctx.modules.session.get(ctx)
        user = User.objects.find_one(username=self.username, active=True)

        sess.user = {
            'is_authenticated': True,
            'is_superuser': user.superuser,
            'username': user.username
        }


class UserLogoutService(UserServiceBase):
    def expire_token(self, token):
        token = UserToken.objects.find_one(token=token)
        token.delete()

    def call(self, ctx):
        sess = ctx.modules.session.get(ctx)
        sess.user = {
            'is_authenticated': False,
            'is_superuser': False,
            'username': None
        }