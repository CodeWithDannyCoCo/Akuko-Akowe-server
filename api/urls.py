from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, admin_views

router = DefaultRouter()
router.register(r'posts', views.PostViewSet)
router.register(r'comments', views.CommentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/signup/', views.signup, name='signup'),
    path('auth/login/', views.login, name='login'),
    path('auth/logout/', views.logout, name='logout'),
    path('users/me/', views.get_current_user, name='current-user'),
    path('users/<str:username>/follow/', views.follow_user, name='follow-user'),
    path('users/<str:username>/unfollow/',
         views.unfollow_user, name='unfollow-user'),
    path('users/<str:username>/activity/',
         views.get_user_activity, name='user-activity'),
    path('users/<str:username>/posts/',
         views.get_user_posts, name='user-posts'),
    path('feed/', views.feed, name='feed'),
    path('users/<str:username>/settings/',
         views.update_user_settings, name='update_user_settings'),
    path('posts/<int:post_id>/like/', views.handle_like, name='handle_like'),
    path('posts/<int:post_id>/bookmark/',
         views.handle_bookmark, name='handle_bookmark'),
    path('users/<str:username>/', views.user_profile, name='user-profile'),

    # Admin endpoints
    path('admin/stats/', admin_views.admin_stats, name='admin-stats'),
    path('admin/analytics/', admin_views.admin_analytics, name='admin-analytics'),
    path('admin/activity/', admin_views.admin_activity, name='admin-activity'),
    path('admin/users/', admin_views.admin_users, name='admin-users'),
    path('admin/users/<int:user_id>/',
         admin_views.admin_users, name='admin-user-detail'),
    path('admin/users/<int:user_id>/role/',
         admin_views.update_user_role, name='admin-user-role'),
    path('admin/posts/', admin_views.admin_posts, name='admin-posts'),
    path('admin/comments/', admin_views.admin_comments, name='admin-comments'),
    path('admin/settings/', admin_views.admin_settings, name='admin-settings'),
]
