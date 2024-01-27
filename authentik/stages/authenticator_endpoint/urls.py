"""API URLs"""
from authentik.stages.authenticator_endpoint.api import (
    AuthenticatorEndpointStageViewSet,
    EndpointAdminDeviceViewSet,
    EndpointDeviceViewSet,
)

api_urlpatterns = [
    ("authenticators/endpoint", EndpointDeviceViewSet),
    (
        "authenticators/admin/endpoint",
        EndpointAdminDeviceViewSet,
        "admin-endpointdevice",
    ),
    ("stages/authenticator/endpoint", AuthenticatorEndpointStageViewSet),
]
