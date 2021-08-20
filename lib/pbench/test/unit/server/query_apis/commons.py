import itertools
import pytest
import requests

from dateutil import parser as date_parser, rrule
from http import HTTPStatus
from typing import AnyStr, Type

from pbench.server.api.resources.query_apis import ElasticBase, JSON, ParamType


class Commons:
    """
    Unit testing for all the elasticsearch resources class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    # Declare the common empty search response payload that subclass can use.
    EMPTY_ES_RESPONSE_PAYLOAD = {
        "took": 1,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
    }

    def _setup(
        self,
        cls_obj: Type[ElasticBase] = None,
        pbench_endpoint: AnyStr = None,
        elastic_endpoint: AnyStr = None,
        payload: JSON = None,
        bad_date_payload: JSON = None,
        error_payload: JSON = None,
        empty_es_response_payload: JSON = None,
    ):
        self.cls_obj = cls_obj
        self.pbench_endpoint = pbench_endpoint
        self.elastic_endpoint = elastic_endpoint
        self.payload = payload
        self.bad_date_payload = bad_date_payload
        self.error_payload = error_payload
        self.empty_es_response_payload = empty_es_response_payload

    def build_index(self, server_config, dates):
        """
        Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        idx = server_config.get("Indexing", "index_prefix") + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def date_range(self, start: AnyStr, end: AnyStr) -> list:
        """
        Builds list of range of dates between start and end
        It expects the date to look like YYYY-MM
        """
        date_range = []
        start_date = date_parser.parse(start)
        end_date = date_parser.parse(end)
        assert start_date <= end_date
        for m in rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date):
            date_range.append(f"{m.year:04}-{m.month:02}")
        return date_range

    def test_non_accessible_user_data(self, client, server_config, pbench_token):
        """
        Test behavior when Authorization header does not have access to other user's data
        """
        # The pbench_token fixture logs in as user "drb"
        # Trying to access the data belong to the user "pp"
        if "user" not in self.cls_obj.schema.parameters.keys():
            pytest.skip("skipping " + self.test_non_accessible_user_data.__name__)
        self.payload["user"] = "pp"
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "user", ("drb", "pp"),
    )
    def test_accessing_user_data_with_invalid_token(
        self, client, server_config, pbench_token, user
    ):
        """
        Test behavior when expired Authorization header provided
        """
        if "user" not in self.cls_obj.schema.parameters.keys():
            pytest.skip(
                "skipping " + self.test_accessing_user_data_with_invalid_token.__name__
            )
        # valid token logout
        response = client.post(
            server_config.rest_uri + "/logout",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.OK
        self.payload["user"] = user
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    def test_missing_keys(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that Pbench will silently ignore any additional keys that are
        specified but not required.
        """

        def missing_key_helper(keys):
            response = client.post(
                server_config.rest_uri + self.pbench_endpoint,
                headers={"Authorization": "Bearer " + pbench_token},
                json=keys,
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST
            missing = [k for k in required_keys if k not in keys]
            assert (
                response.json.get("message")
                == f"Missing required parameters: {','.join(missing)}"
            )

        parameter_items = self.cls_obj.schema.parameters.items()

        required_keys = [
            key for key, parameter in parameter_items if parameter.required
        ]

        all_combinations = []
        for r in range(1, len(parameter_items) + 1):
            for item in itertools.combinations(parameter_items, r):
                tmp_req_keys = [key for key, parameter in item if parameter.required]
                if tmp_req_keys != required_keys:
                    all_combinations.append(item)

        for items in all_combinations:
            keys = {}
            for key, parameter in items:
                if parameter.type == ParamType.ACCESS:
                    keys[key] = "public"
                elif parameter.type == ParamType.DATE:
                    keys[key] = "2020"
                else:
                    keys[key] = "foobar"

            missing_key_helper(keys)

        # Test in case all of the required keys are missing and some
        # random non-existent key is present in the payload
        if required_keys:
            missing_key_helper({"notakey": None})

    def test_bad_dates(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        for key, p in self.cls_obj.schema.parameters.items():
            # Modify date/time key in the payload to make it look invalid
            if p.type == ParamType.DATE and key in self.payload:
                original_date_value = self.payload[key]
                self.payload[key] = "2020-19"
                response = client.post(
                    server_config.rest_uri + self.pbench_endpoint,
                    headers={"Authorization": "Bearer " + pbench_token},
                    json=self.payload,
                )
                assert response.status_code == HTTPStatus.BAD_REQUEST
                assert (
                    response.json.get("message")
                    == "Value '2020-19' (str) cannot be parsed as a date/time string"
                )
                self.payload[key] = original_date_value

    def test_empty_query(
        self,
        client,
        server_config,
        query_api,
        user_ok,
        find_template,
        build_auth_header,
    ):
        """
        Check proper handling of a query resulting in no Elasticsearch matches.
        PyTest will run this test multiple times with different values of the build_auth_header
        fixture.
        """
        if not self.empty_es_response_payload or not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_empty_query.__name__)
        expected_status = HTTPStatus.OK
        if build_auth_header["header_param"] != "valid":
            expected_status = HTTPStatus.FORBIDDEN

        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )
        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            headers=build_auth_header["header"],
            status=HTTPStatus.OK,
            json=self.empty_es_response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            assert response.json == []

    @pytest.mark.parametrize(
        "exceptions",
        (
            {
                "exception": requests.exceptions.ConnectionError(),
                "status": HTTPStatus.BAD_GATEWAY,
            },
            {
                "exception": requests.exceptions.Timeout(),
                "status": HTTPStatus.GATEWAY_TIMEOUT,
            },
            {
                "exception": requests.exceptions.InvalidURL(),
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            },
            {"exception": Exception(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
            {"exception": ValueError(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
        ),
    )
    def test_http_exception(
        self,
        server_config,
        query_api,
        exceptions,
        user_ok,
        find_template,
        pbench_token,
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        if not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_http_exception.__name__)

        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            exceptions["status"],
            body=exceptions["exception"],
            headers={"Authorization": "Bearer " + pbench_token},
        )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(
        self, server_config, query_api, user_ok, find_template, pbench_token, errors
    ):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        if not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_http_error.__name__)

        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
            headers={"Authorization": "Bearer " + pbench_token},
        )