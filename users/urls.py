from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

urlpatterns = [
    # ============================================================
    # TOKEN MANAGEMENT (JWT)
    # ============================================================
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # ============================================================
    # AUTHENTICATION
    # ============================================================
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # ============================================================
    # PROFILE MANAGEMENT
    # ============================================================
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/preferences/', views.UserPreferencesView.as_view(), name='preferences'),
    
    # ============================================================
    # PASSWORD MANAGEMENT
    # ============================================================
    path('password/change/', views.ChangePasswordView.as_view(), name='change_password'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # ============================================================
    # VERIFICATION
    # ============================================================
    path('verify/email/', views.VerifyEmailView.as_view(), name='verify_email'),
    path('verify/phone/', views.VerifyPhoneView.as_view(), name='verify_phone'),
    
    # ============================================================
    # USER MANAGEMENT (ADMIN)
    # ============================================================
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<int:id>/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/search/', views.UserSearchView.as_view(), name='user_search'),
    path('stats/', views.UserStatsView.as_view(), name='user_stats'),
]