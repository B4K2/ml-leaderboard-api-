from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated 
from rest_framework.views import APIView
from tasks.models import Submission
import random

from .serializers import (
    UserRegistrationSerializer, 
    VerifyOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    MyTokenObtainPairSerializer,
    UserProfileSerializer
)

FACE_EMOJIS = ['😀', '😎', '😊', '🥳', '😇', '🤓', '🤩', '😁', '😂', '🙂']

class MyTokenObtainPairView(TokenObtainPairView):
    """
    This view uses our custom serializer to log in with a username.
    """
    serializer_class = MyTokenObtainPairSerializer

User = get_user_model()

# --- Helper Functions ---
def generate_otp(length=6):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

# --- API Views ---

class RegisterView(generics.GenericAPIView): # Changed from CreateAPIView
    serializer_class = UserRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = serializer.validated_data
        email = validated_data['email']

        # Don't save the user yet. Instead, prepare the data for caching.
        user_data = {
            'username': validated_data['username'],
            'email': email,
            'password': make_password(validated_data['password']), # Hash the password!
        }

        # Generate and cache OTP along with user data
        otp = generate_otp()
        cache.set(f"reg_{email}", {'user_data': user_data, 'otp': otp}, timeout=600) # 10-minute expiry

        # Send OTP email
        send_mail(
            subject='Your Account Verification Code',
            message=f'Your verification code is: {otp}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        return Response(
            {"message": "Registration successful. Please check your email for the OTP."},
            status=status.HTTP_200_OK # Changed from 201
        )

class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        cached_data = cache.get(f"reg_{email}")

        if cached_data is None:
            return Response({"error": "OTP has expired or is invalid. Please register again."}, status=status.HTTP_400_BAD_REQUEST)

        if cached_data['otp'] != otp:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)
        
        # OTP is correct, now create the user from cached data
        user_data = cached_data['user_data']
        
        try:
            user = User.objects.create(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'] # The password is already hashed
            )
            user.is_active = True
            user.email_verified = True
            user.avatar_emoji = random.choice(FACE_EMOJIS)
            user.save()
        except Exception as e:
            # This could happen in a rare race condition
            return Response({"error": "User with this username or email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Clean up the cache
        cache.delete(f"reg_{email}")

        return Response({"message": "Email verified successfully. You can now log in."}, status=status.HTTP_200_OK)


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        user = User.objects.get(email=email)

        # Generate token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Construct reset link (frontend URL)
        reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/" # Update with your frontend URL

        # Send email
        send_mail(
            subject='Password Reset Request',
            message=f'Click the link to reset your password: {reset_link}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

        return Response({"message": "Password reset link has been sent to your email."}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, uidb64, token, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            # Catch the specific validation error and return its details
            return Response({"error": e.messages}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Catch any other potential validation errors
            return Response({"error": "Invalid data provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(serializer.validated_data['password'])
            user.save()
            return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid token or user ID."}, status=status.HTTP_400_BAD_REQUEST)
        
class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated] # This locks the view
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user
    
class UserStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Calculate Total Submissions
        total_submissions = Submission.objects.filter(user=user).count()
        
        stats_data = {
            'total_submissions': total_submissions,
            'current_rank': 'N/A', # Placeholder
            'best_rank': 'N/A'     # Placeholder
        }
        
        return Response(stats_data, status=status.HTTP_200_OK)