from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Post, User, Like, Bookmark, Follow, Comment
from .serializers import PostSerializer, UserSerializer, UserProfileSerializer, LikeSerializer, BookmarkSerializer, FollowSerializer, CommentSerializer
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import jwt
from datetime import datetime, timedelta

User = get_user_model()


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    Create a new user account
    """
    try:
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            response_data = {
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        return Response(
            {'detail': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)

    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'token': str(refresh.access_token),
            'refresh': str(refresh),
        })
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET', 'PUT'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
def user_profile(request, username):
    """Combined view for getting and updating user profiles"""
    user = get_object_or_404(User, username=username)

    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)

    elif request.method == 'PUT':
        if request.user.username != username:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Create a mutable copy of the request data
        data = request.data.dict() if hasattr(
            request.data, 'dict') else request.data.copy()

        # Handle file upload separately
        if 'avatar' in request.FILES:
            data['avatar'] = request.FILES['avatar']

        serializer = UserSerializer(user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_user_posts(request, username):
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(author=user)
    serializer = PostSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
def get_user_activity(request, username):
    user = get_object_or_404(User, username=username)
    likes = Like.objects.filter(user=user)
    comments = Comment.objects.filter(author=user)
    bookmarks = Bookmark.objects.filter(user=user)
    return Response({
        'likes': LikeSerializer(likes, many=True).data,
        'comments': CommentSerializer(comments, many=True).data,
        'bookmarks': BookmarkSerializer(bookmarks, many=True).data,
    })


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def handle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        Like.objects.get_or_create(user=request.user, post=post)
        return Response({
            'status': 'liked',
            'likes_count': post.post_likes.count(),
            'is_liked': True
        })
    elif request.method == 'DELETE':
        Like.objects.filter(user=request.user, post=post).delete()
        return Response({
            'status': 'unliked',
            'likes_count': post.post_likes.count(),
            'is_liked': False
        })


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def handle_bookmark(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        Bookmark.objects.get_or_create(user=request.user, post=post)
        return Response({
            'status': 'bookmarked',
            'bookmarks_count': post.post_bookmarks.count(),
            'is_bookmarked': True
        })
    elif request.method == 'DELETE':
        Bookmark.objects.filter(user=request.user, post=post).delete()
        return Response({
            'status': 'unbookmarked',
            'bookmarks_count': post.post_bookmarks.count(),
            'is_bookmarked': False
        })


@api_view(['POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def handle_follow(request, username):
    user_to_follow = get_object_or_404(User, username=username)
    if request.method == 'POST':
        Follow.objects.get_or_create(
            follower=request.user, following=user_to_follow)
        return Response({'status': 'following'})
    elif request.method == 'DELETE':
        Follow.objects.filter(follower=request.user,
                              following=user_to_follow).delete()
        return Response({'status': 'unfollowed'})


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_profile_picture(request, username):
    if request.user.username != username:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    if 'avatar' not in request.FILES:
        return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

    request.user.avatar = request.FILES['avatar']
    request.user.save()
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def feed(request):
    following = Follow.objects.filter(
        follower=request.user).values_list('following', flat=True)
    posts = Post.objects.filter(author__in=following).order_by('-created_at')
    serializer = PostSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data["refresh_token"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'status': 'logged out'})
    except Exception:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        queryset = Comment.objects.all()
        post_id = self.request.query_params.get('post', None)
        if post_id is not None:
            queryset = queryset.filter(post_id=post_id)
        return queryset


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_user(request, username):
    if request.user.username != username:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    user = request.user
    # Create a mutable copy of the request data
    data = request.data.dict() if hasattr(
        request.data, 'dict') else request.data.copy()

    # Handle file upload separately
    if 'avatar' in request.FILES:
        data['avatar'] = request.FILES['avatar']

    serializer = UserSerializer(user, data=data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_user_settings(request, username):
    if request.user.username != username:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

    user = request.user
    # Add any settings-specific logic here
    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def follow_user(request, username):
    user_to_follow = get_object_or_404(User, username=username)
    Follow.objects.get_or_create(
        follower=request.user, following=user_to_follow)
    return Response({'status': 'following'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def unfollow_user(request, username):
    user_to_follow = get_object_or_404(User, username=username)
    Follow.objects.filter(follower=request.user,following=user_to_follow).delete()
    return Response({'status': 'unfollowed'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_current_user(request):
    """Get the current authenticated user's profile"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([])  # No authentication required
def health_check(request):
    """
    Health check endpoint to verify API availability
    """
    try:
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return Response({
            "status": "healthy",
            "message": "API is running",
            "database": "connected",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            "status": "unhealthy",
            "message": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Request a password reset by providing an email address
    """
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        # Generate reset token
        token = jwt.encode({
            'user_id': user.id,
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, settings.SECRET_KEY, algorithm='HS256')

        # Create reset URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}&email={email}"

        # Send email
        send_mail(
            'Password Reset Request',
            f'Click the following link to reset your password: {reset_url}',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return Response({
            'message': 'Password reset email sent successfully',
            'email': email
        })
    except User.DoesNotExist:
        # For security, don't reveal if the email exists or not
        return Response({
            'message': 'If an account exists with this email, a password reset link will be sent.',
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """
    Confirm password reset by providing token, email, and new password
    """
    token = request.data.get('token')
    email = request.data.get('email')
    password = request.data.get('password')

    if not all([token, email, password]):
        return Response({
            'error': 'Token, email, and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Verify token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        
        # Check if token matches email
        if payload['email'] != email:
            return Response({
                'error': 'Invalid token for this email'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get user and update password
        user = User.objects.get(id=payload['user_id'])
        user.set_password(password)
        user.save()

        return Response({
            'message': 'Password reset successful'
        })
    except jwt.ExpiredSignatureError:
        return Response({
            'error': 'Reset token has expired'
        }, status=status.HTTP_400_BAD_REQUEST)
    except jwt.InvalidTokenError:
        return Response({
            'error': 'Invalid reset token'
        }, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
