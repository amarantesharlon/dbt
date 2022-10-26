from abc import ABCMeta, abstractmethod
import json
from typing import Any, Dict
import requests
from requests import Response
from urllib.parse import urlencode


class BaseHttp(metaclass=ABCMeta):
    @abstractmethod
    def get_json(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_response(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Response:
        raise NotImplementedError

    @abstractmethod
    def post(
        self,
        url: str,
        data: Any = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Response:
        raise NotImplementedError


class PyodideHttp(BaseHttp):
    def __init__(self) -> None:
        super().__init__()
        from pyodide.http import open_url  # type: ignore

        self._open_url = open_url

    def get_json(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        if params is not None:
            url += f"?{urlencode(params)}"
        r = self._open_url(url=url)
        return json.load(r)

    def get_response(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Response:
        raise NotImplementedError

    def post(
        self,
        url: str,
        data: Any = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Response:
        raise NotImplementedError


class Requests(BaseHttp):
    def get_json(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Dict[str, Any]:
        return self.get_response(url=url, params=params, timeout=timeout).json()

    def get_response(
        self,
        url: str,
        params: Dict[str, Any] = None,
        timeout: int = None,
    ) -> Response:
        return requests.get(url=url, params=params, timeout=timeout)

    def post(
        self,
        url: str,
        data: Any = None,
        headers: Dict[str, str] = None,
        timeout: int = None,
    ) -> Response:
        return requests.post(url=url, data=data, headers=headers, timeout=timeout)


class Http:
    def __init__(self, is_pyodide: bool) -> None:
        self.client = PyodideHttp() if is_pyodide else Requests()
