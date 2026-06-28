from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow owner to edit their own object, read-only for others
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to owner
        return obj.user == request.user or obj == request.user


class IsVerifiedUser(permissions.BasePermission):
    """
    Allow access only to verified users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_verified


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allow owner or admin to access
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.is_staff


class CanManageOrders(permissions.BasePermission):
    """
    Allow user to view/manage their own orders
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Owner can view their order
        if obj.customer == request.user:
            return True
        # Staff can manage all orders
        return request.user.is_staff


class CanManagePayments(permissions.BasePermission):
    """
    Allow user to view/manage their own payments
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Owner can view payment for their order
        if obj.order.customer == request.user:
            return True
        # Staff can manage all payments
        return request.user.is_staff


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow admin to edit, anyone to read
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsProductAdmin(permissions.BasePermission):
    """
    Allow only product admins to manage products
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class HasEmailVerification(permissions.BasePermission):
    """
    Allow access only to email-verified users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.email_verified


class HasPhoneVerification(permissions.BasePermission):
    """
    Allow access only to phone-verified users
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.phone_verified


class CanCreateOrders(permissions.BasePermission):
    """
    Allow creation of orders only for verified users with complete profile
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return (request.user and 
                    request.user.is_authenticated and 
                    request.user.is_verified)
        return True