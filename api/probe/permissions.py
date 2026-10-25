from rest_framework import permissions


class IsProbeCarOwner(permissions.BasePermission):
    # for view permission
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    # for object level permissions
    def has_object_permission(self, request, view, car_obj):
        return car_obj.car.owner.id == request.user.id