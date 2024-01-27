"""AuthenticatorEndpointStage API Views"""
from django.http import Http404
from django_filters.rest_framework.backends import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.fields import CharField, ChoiceField, IntegerField
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet
from structlog.stdlib import get_logger
from rest_framework.permissions import AllowAny

from authentik.api.authorization import OwnerFilter, OwnerPermissions
from authentik.api.decorators import permission_required
from authentik.core.api.used_by import UsedByMixin
from authentik.flows.api.stages import StageSerializer
from authentik.stages.authenticator_endpoint.models import (
    AuthenticatorEndpointStage,
    EndpointDevice,
)

LOGGER = get_logger()


class AuthenticatorEndpointStageSerializer(StageSerializer):
    """AuthenticatorEndpointStage Serializer"""

    class Meta:
        model = AuthenticatorEndpointStage
        fields = StageSerializer.Meta.fields + [
            "configure_flow",
            "friendly_name",
        ]


class AuthenticatorEndpointStageViewSet(UsedByMixin, ModelViewSet):
    """AuthenticatorEndpointStage Viewset"""

    queryset = AuthenticatorEndpointStage.objects.all()
    serializer_class = AuthenticatorEndpointStageSerializer
    filterset_fields = [
        "name",
        "configure_flow",
    ]
    search_fields = ["name"]
    ordering = ["name"]


class EndpointDeviceSerializer(ModelSerializer):
    """Serializer for Endpoint authenticator devices"""

    class Meta:
        model = EndpointDevice
        fields = ["pk", "name"]
        depth = 2


class EndpointDeviceViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    UsedByMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    """Viewset for Endpoint authenticator devices"""

    queryset = EndpointDevice.objects.all()
    serializer_class = EndpointDeviceSerializer
    search_fields = ["name"]
    filterset_fields = ["name"]
    ordering = ["name"]
    permission_classes = [OwnerPermissions]
    filter_backends = [OwnerFilter, DjangoFilterBackend, OrderingFilter, SearchFilter]

    @action(methods=["POST"], detail=False, permission_classes=[AllowAny])
    def osquery_enroll(self, request: Request) -> Response:
        # EndpointDevice.objects.create(host_identifier=request.data.get("host_identifier"))
        print(request.data)
        return Response({"node_key": "test-key", "node_invalid": False})

    @action(methods=["POST"], detail=False, permission_classes=[AllowAny])
    def osquery_config(self, request: Request) -> Response:
        print(request.data)
        return Response(
            {
                "schedule": {
                    # "macos_kextstat": {"query": "SELECT * FROM kernel_extensions;", "interval": 10},
                    "foobar": {"query": "select * from uptime;", "interval": 600},
                },
                "node_invalid": False,
            }
        )

    @action(methods=["POST"], detail=False, permission_classes=[AllowAny])
    def osquery_log(self, request: Request) -> Response:
        print(request.data)
        return Response({"schedule": {}, "node_invalid": False})


class EndpointAdminDeviceViewSet(ModelViewSet):
    """Viewset for Endpoint authenticator devices (for admins)"""

    permission_classes = [IsAdminUser]
    queryset = EndpointDevice.objects.all()
    serializer_class = EndpointDeviceSerializer
    search_fields = ["name"]
    filterset_fields = ["name"]
    ordering = ["name"]
