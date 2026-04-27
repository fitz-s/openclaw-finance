#!/usr/bin/env python3
"""Finance-side Google runtime compatibility helpers for TradingAgents."""
from __future__ import annotations

import importlib
from typing import Any


def detect_google_adc() -> dict[str, Any]:
    """Return local ADC availability for Google runtimes."""
    try:
        google_auth = importlib.import_module('google.auth')
        credentials, project = google_auth.default()
        return {
            'available': True,
            'project': project,
            'credential_type': credentials.__class__.__name__,
            'error_class': None,
            'error_message': None,
        }
    except Exception as exc:
        return {
            'available': False,
            'project': None,
            'credential_type': None,
            'error_class': exc.__class__.__name__,
            'error_message': str(exc),
        }


def patch_google_runtime(graph_mod: Any, google_client_mod: Any) -> None:
    """Patch TradingAgents Google runtime to support ADC/Vertex AI when requested."""
    if getattr(google_client_mod.GoogleClient, '_finance_adc_patch_applied', False):
        return

    original_get_provider_kwargs = graph_mod.TradingAgentsGraph._get_provider_kwargs
    original_get_llm = google_client_mod.GoogleClient.get_llm
    normalized_chat = google_client_mod.NormalizedChatGoogleGenerativeAI

    def patched_get_provider_kwargs(self) -> dict[str, Any]:
        kwargs = original_get_provider_kwargs(self)
        if str(self.config.get('llm_provider') or '').lower() != 'google':
            return kwargs
        if self.config.get('google_use_application_default_credentials') is True:
            kwargs['use_application_default_credentials'] = True
        if 'google_vertexai' in self.config:
            kwargs['vertexai'] = bool(self.config.get('google_vertexai'))
        if self.config.get('google_location'):
            kwargs['location'] = self.config.get('google_location')
        return kwargs

    def patched_get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {'model': self.model}

        if self.base_url:
            llm_kwargs['base_url'] = self.base_url

        passthrough_keys = (
            'timeout',
            'max_retries',
            'callbacks',
            'http_client',
            'http_async_client',
            'location',
            'vertexai',
        )
        for key in passthrough_keys:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        google_api_key = self.kwargs.get('api_key') or self.kwargs.get('google_api_key')
        if google_api_key:
            llm_kwargs['google_api_key'] = google_api_key
        elif self.kwargs.get('use_application_default_credentials'):
            google_auth = importlib.import_module('google.auth')
            credentials, project = google_auth.default()
            llm_kwargs['credentials'] = credentials
            if project:
                llm_kwargs['project'] = project
            llm_kwargs['vertexai'] = bool(self.kwargs.get('vertexai', True))
            llm_kwargs['location'] = str(self.kwargs.get('location') or 'global')

        thinking_level = self.kwargs.get('thinking_level')
        if thinking_level:
            model_lower = self.model.lower()
            if 'gemini-3' in model_lower:
                if 'pro' in model_lower and thinking_level == 'minimal':
                    thinking_level = 'low'
                llm_kwargs['thinking_level'] = thinking_level
            else:
                llm_kwargs['thinking_budget'] = -1 if thinking_level == 'high' else 0

        return normalized_chat(**llm_kwargs)

    graph_mod.TradingAgentsGraph._get_provider_kwargs = patched_get_provider_kwargs
    google_client_mod.GoogleClient.get_llm = patched_get_llm
    google_client_mod.GoogleClient._finance_adc_patch_applied = True
    google_client_mod.GoogleClient._finance_original_get_llm = original_get_llm


def patch_yfinance_dataflow(y_finance_mod: Any) -> None:
    """Patch TradingAgents y_finance helpers for missing local imports."""
    if getattr(y_finance_mod, '_finance_dataflow_patch_applied', False):
        return
    if not hasattr(y_finance_mod, 'pd'):
        y_finance_mod.pd = importlib.import_module('pandas')
    y_finance_mod._finance_dataflow_patch_applied = True
