from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Post, User, Like, Bookmark, Follow, Comment, SiteSettings


class UserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['bio', 'avatar', 'website', 'avatar_url']

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'bio', 'avatar',
                  'website', 'date_joined', 'followers_count', 'following_count',
                  'posts_count', 'is_staff', 'avatar_url')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': False},
            'username': {'required': False},
            'bio': {'required': False},
            'avatar': {'required': False},
            'website': {'required': False}
        }

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()

    def get_posts_count(self, obj):
        return obj.post_set.count()

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def create(self, validated_data):
        if 'password' not in validated_data:
            raise serializers.ValidationError(
                {'password': 'This field is required.'})

        # Create user with default profile data
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            bio=validated_data.get('bio', ''),  # Default empty bio
            website=validated_data.get('website', ''),  # Default empty website
        )

        # Create initial activity record
        from .models import UserActivity
        UserActivity.objects.create(
            user=user,
            activity_type='join',
            content=f'User {user.username} joined the platform'
        )

        return user

    def update(self, instance, validated_data):
        # Handle password updates separately
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    likes_count = serializers.SerializerMethodField()
    bookmarks_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'author', 'created_at', 'updated_at',
                  'likes_count', 'bookmarks_count', 'comments_count', 'is_liked', 'is_bookmarked']

    def get_likes_count(self, obj):
        return obj.post_likes.count()

    def get_bookmarks_count(self, obj):
        return obj.post_bookmarks.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.post_likes.filter(user=request.user).exists()
        return False

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.post_bookmarks.filter(user=request.user).exists()
        return False


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'user', 'post', 'created_at']


class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'post', 'created_at']


class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'follower', 'following', 'created_at']


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    author_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'author_avatar',
                  'content', 'created_at', 'updated_at']
        read_only_fields = ['author']

    def get_author_avatar(self, obj):
        if obj.author.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.author.avatar.url)
            return obj.author.avatar.url
        return None


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'maintenance_mode',
                  'allow_registration', 'default_user_role', 'updated_at']
        read_only_fields = ['updated_at']
