"""Kerberos source SPNEGO views"""
from base64 import b64decode, b64encode

import gssapi
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.views import View
from structlog.stdlib import get_logger

from authentik.core.sources.flow_manager import SourceFlowManager
from authentik.sources.kerberos.models import (
    KerberosSource,
    Krb5ConfContext,
    UserKerberosSourceConnection,
)

LOGGER = get_logger()

SPNEGO_REQUEST_STATUS = 401
WWW_AUTHENTICATE = "WWW-Authenticate"
HTTP_AUTHORIZATION = "Authorization"
NEGOTIATE = "Negotiate"

SPNEGO_STATE_CACHE_PREFIX = "goauthentik.io/sources/spnego"
SPNEGO_STATE_CACHE_TIMEOUT = 60 * 5  # 5 minutes


class SPNEGOView(View):
    """SPNEGO login"""

    source: KerberosSource

    def challenge(self, request, token: str | None = None) -> HttpResponse:
        """Get SNPEGO challenge response"""
        response = render(
            request,
            "if/error.html",
            context={
                "title": _("SPNEGO authentication required"),
                "message": _("""
                    Make sure you have valid tickets (obtainable via kinit) and configured the browser correctly.
                    You can find out more at https://goauthentik.io/integrations/sources/spnego/browser
                """),
            },
            status=401,
        )
        response[WWW_AUTHENTICATE] = (
            NEGOTIATE if token is None else f"{NEGOTIATE} {b64encode(token).decode('ascii')}"
        )
        return response

    def get_authstr(self, request) -> str | None:
        """Get SPNEGO authentication string from headers"""
        authorization_header = request.headers.get(HTTP_AUTHORIZATION, "")
        if NEGOTIATE.lower() not in authorization_header.lower():
            return None

        auth_tuple = authorization_header.split(" ", 1)
        if not auth_tuple or auth_tuple[0].lower() != NEGOTIATE.lower():
            return None
        if len(auth_tuple) != 2:
            raise SuspiciousOperation("Malformed authorization header")
        return auth_tuple[1]

    def new_state(self) -> str:
        """Generate request state"""
        return get_random_string(32)

    def get_server_ctx(self, key: str) -> gssapi.sec_contexts.SecurityContext | None:
        """Get GSSAPI server context from cache or create it"""
        server_creds = self.source.get_gssapi_creds()
        if server_creds is None:
            return None

        state = cache.get(f"{SPNEGO_STATE_CACHE_PREFIX}/{key}", None)

        if state:
            # pylint: disable=c-extension-no-member
            return gssapi.sec_contexts.SecurityContext(
                base=gssapi.raw.sec_contexts.import_sec_context(state),
            )

        return gssapi.sec_contexts.SecurityContext(creds=server_creds, usage="accept")

    def set_server_ctx(self, key: str, ctx: gssapi.sec_contexts.SecurityContext):
        """Store the GSSAPI server context in cache"""
        cache.set(f"{SPNEGO_STATE_CACHE_PREFIX}/{key}", ctx.export(), SPNEGO_STATE_CACHE_TIMEOUT)

    # pylint: disable=too-many-return-statements
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        """Process SPNEGO request"""
        self.source: KerberosSource = get_object_or_404(
            KerberosSource, slug=kwargs.get("source_slug", "")
        )
        if not self.source.enabled:
            raise Http404

        qstring = request.GET if request.method == "GET" else request.POST
        state = qstring.get("state", None)
        if not state:
            return redirect(
                reverse(
                    "authentik_sources_kerberos:spnego-login",
                    kwargs={"source_slug": self.source.slug},
                )
                + f"?state={self.new_state()}"
            )

        authstr = self.get_authstr(request)
        if not authstr:
            LOGGER.debug("authstr not present, sending challenge")
            return self.challenge(request)

        try:
            in_token = b64decode(authstr)
        except (TypeError, ValueError):
            return self.challenge(request)

        with Krb5ConfContext(self.source):
            server_ctx = self.get_server_ctx(state)
            if not server_ctx:
                return self.challenge(request)

            try:
                out_token = server_ctx.step(in_token)
            except gssapi.exceptions.GSSError as exc:
                LOGGER.debug("GSSAPI security context failure", exc=exc)
                return self.challenge(request)

            if not server_ctx.complete or server_ctx.initiator_name is None:
                self.set_server_ctx(state, server_ctx)
                return self.challenge(request, out_token)

            # TODO: property mappings
            identifier = str(server_ctx.initiator_name)
            enroll_info = {
                "username": identifier if "@" not in identifier else identifier.rsplit("@", 1)[0],
                "email": "",
                "name": "",
            }

        sfm = SPNEGOSourceFlowManager(
            source=self.source,
            request=request,
            identifier=identifier,
            enroll_info=enroll_info,
        )
        sfm.policy_context = {
            "spnego_info": {
                "initiator_name": str(server_ctx.initiator_name),
                "target_name": str(server_ctx.target_name),
                "mech": str(server_ctx.mech),
                "actual_flags": server_ctx.actual_flags,
            }
        }
        return sfm.get_flow()


class SPNEGOSourceFlowManager(SourceFlowManager):
    """Flow manager for Kerberos SPNEGO sources"""

    connection_type = UserKerberosSourceConnection