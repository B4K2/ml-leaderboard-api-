from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        # You can add more email validation if needed, e.g., checking the domain
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})

        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        # We create the user as inactive until they verify their email
        user.is_active = False
        user.save()
        return user

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("No active user found with this email address.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
class MyTokenObtainPairSerializer(serializers.Serializer):
    # We define the fields the serializer expects
    identifier = serializers.CharField(required=True)  # can be email or username
    password = serializers.CharField(required=True, write_only=True)
    
    # We remove the old get_token classmethod as we will handle it here

    def validate(self, attrs):
        identifier = attrs.get("identifier")
        password = attrs.get("password")
        user = None

        # Try to find the user by email first
        try:
            user = User.objects.get(email=identifier)
        except User.DoesNotExist:
            # If not found by email, try by username
            try:
                user = User.objects.get(username=identifier)
            except User.DoesNotExist:
                # If still not found, authentication fails
                pass

        # Check the password if a user was found
        if user and user.check_password(password):
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")

            # --- THIS IS THE CRITICAL FIX ---
            # If authentication is successful, we manually generate the tokens.
            refresh = RefreshToken.for_user(user)

            # You can add custom claims to the token here
            refresh['username'] = user.username
            refresh['email'] = user.email

            # The data to be returned
            data = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            return data

        # If user not found or password is wrong, raise the generic error
        raise serializers.ValidationError("No active account found with the given credentials")
    
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']