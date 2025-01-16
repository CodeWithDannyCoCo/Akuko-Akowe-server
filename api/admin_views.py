from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from .models import User, Post, Comment, Like, Bookmark, SiteSettings
from .serializers import UserSerializer, PostSerializer, CommentSerializer, SiteSettingsSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_stats(request):
    """Get admin dashboard statistics"""
    now = timezone.now()
    last_month = now - timedelta(days=30)

    # Get current counts
    users_count = User.objects.count()
    posts_count = Post.objects.count()
    comments_count = Comment.objects.count()

    # Get last month's counts for trend calculation
    last_month_users = User.objects.filter(date_joined__lt=last_month).count()
    last_month_posts = Post.objects.filter(created_at__lt=last_month).count()
    last_month_comments = Comment.objects.filter(
        created_at__lt=last_month).count()

    # Calculate engagement (likes + comments + bookmarks per post)
    total_interactions = Like.objects.count() + Comment.objects.count() + \
        Bookmark.objects.count()
    engagement_rate = (total_interactions / posts_count *
                       100) if posts_count > 0 else 0

    # Calculate trends (percentage change)
    def calculate_trend(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100

    return Response({
        'users': {
            'total': users_count,
            'trend': calculate_trend(users_count, last_month_users)
        },
        'posts': {
            'total': posts_count,
            'trend': calculate_trend(posts_count, last_month_posts)
        },
        'comments': {
            'total': comments_count,
            'trend': calculate_trend(comments_count, last_month_comments)
        },
        'engagement': {
            'total': round(engagement_rate, 1),
            'trend': 0  # TODO: Calculate engagement trend
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_activity(request):
    """Get recent admin activity"""
    # Get recent user registrations
    recent_users = User.objects.order_by('-date_joined')[:5]
    # Get recent posts
    recent_posts = Post.objects.order_by('-created_at')[:5]
    # Get recent comments
    recent_comments = Comment.objects.order_by('-created_at')[:5]

    activity = []

    # Add user registrations to activity
    for user in recent_users:
        activity.append({
            'id': f'user_{user.id}',
            'type': 'success',
            'message': f'New user registered: {user.username}',
            'timestamp': user.date_joined,
            'icon': 'Users'
        })

    # Add posts to activity
    for post in recent_posts:
        activity.append({
            'id': f'post_{post.id}',
            'type': 'info',
            'message': f'New post created by {post.author.username}',
            'timestamp': post.created_at,
            'icon': 'FileText'
        })

    # Add comments to activity
    for comment in recent_comments:
        activity.append({
            'id': f'comment_{comment.id}',
            'type': 'info',
            'message': f'New comment by {comment.author.username}',
            'timestamp': comment.created_at,
            'icon': 'MessageSquare'
        })

    # Sort by timestamp
    activity.sort(key=lambda x: x['timestamp'], reverse=True)

    return Response(activity[:10])  # Return only the 10 most recent activities


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_users(request, user_id=None):
    """Manage users from admin dashboard"""
    if request.method == 'GET':
        users = User.objects.all()
        serializer = UserSerializer(
            users, many=True, context={'request': request})
        return Response(serializer.data)

    elif request.method == 'PUT':
        user = User.objects.get(id=user_id)
        serializer = UserSerializer(
            user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        user = User.objects.get(id=user_id)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_posts(request):
    """Get all posts with admin details"""
    posts = Post.objects.all().order_by('-created_at')
    serializer = PostSerializer(posts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_comments(request):
    """Get all comments with admin details"""
    comments = Comment.objects.all().order_by('-created_at')
    serializer = CommentSerializer(
        comments, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_settings(request):
    """Manage admin settings"""
    settings = SiteSettings.get_settings()

    if request.method == 'GET':
        serializer = SiteSettingsSerializer(settings)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = SiteSettingsSerializer(
            settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_user_role(request, user_id):
    """Update a user's role"""
    try:
        user = User.objects.get(id=user_id)
        new_role = request.data.get('role')

        if new_role not in ['user', 'staff']:
            return Response(
                {'error': 'Invalid role specified'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update user's staff status based on role
        user.is_staff = (new_role == 'staff')
        user.save()

        return Response({
            'message': f'User role updated to {new_role}',
            'user': UserSerializer(user).data
        })
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def admin_analytics(request):
    """Get time-series analytics data for charts"""
    time_range = request.GET.get('range', 'week')
    now = timezone.now()

    if time_range == 'week':
        days = 7
        interval = 'day'
    elif time_range == 'month':
        days = 30
        interval = 'day'
    else:  # year
        days = 365
        interval = 'month'

    start_date = now - timedelta(days=days)

    # Generate date ranges
    if interval == 'day':
        dates = [(start_date + timedelta(days=x)).strftime('%Y-%m-%d')
                 for x in range(days)]
    else:
        dates = [(start_date + timedelta(days=x*30)).strftime('%Y-%m')
                 for x in range(12)]

    # Get user signups over time
    user_data = []
    for date in dates:
        if interval == 'day':
            count = User.objects.filter(
                date_joined__date=date
            ).count()
        else:
            count = User.objects.filter(
                date_joined__year=date.split('-')[0],
                date_joined__month=date.split('-')[1]
            ).count()
        user_data.append(count)

    # Get post creation data
    post_data = []
    for date in dates:
        if interval == 'day':
            count = Post.objects.filter(
                created_at__date=date
            ).count()
        else:
            count = Post.objects.filter(
                created_at__year=date.split('-')[0],
                created_at__month=date.split('-')[1]
            ).count()
        post_data.append(count)

    # Get engagement data (likes + comments)
    engagement_data = []
    for date in dates:
        if interval == 'day':
            likes = Like.objects.filter(created_at__date=date).count()
            comments = Comment.objects.filter(created_at__date=date).count()
        else:
            likes = Like.objects.filter(
                created_at__year=date.split('-')[0],
                created_at__month=date.split('-')[1]
            ).count()
            comments = Comment.objects.filter(
                created_at__year=date.split('-')[0],
                created_at__month=date.split('-')[1]
            ).count()
        engagement_data.append(likes + comments)

    return Response({
        'dates': dates,
        'users': user_data,
        'posts': post_data,
        'engagement': engagement_data
    })
