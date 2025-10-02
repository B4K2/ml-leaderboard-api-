from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom user model where email is the unique identifier for authentication.
    """
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)

    # Use email as the username field
    USERNAME_FIELD = 'email'
    # 'username' is still required for Django's internal workings (like createsuperuser)
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email