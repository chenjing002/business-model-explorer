"""Static API: unit safety, null preservation, sharding and ranking fidelity."""
import json

import pytest

from pipeline.agent_data import API, history, stage_catalog
from pipeline.pages import company_url, bundle_url


def test_history_preserves_units_missing_reasons_and_year_specific_definitions():
    bundle = {'ts_code': '000651.SZ', 'unit': 'CNY_yuan', 'calculation_details': {
        '20231231': {
            'rnoa': {'label': '净经营资产收益率', 'unit': 'pct', 'value': None, 'reason': 'no_opening_balance', 'formula': '旧口径'},
            'market_cap': {'label': '总市值', 'unit': 'CNY_yuan', 'value': 123456789},
            'shares': {'label': '总股本', 'unit': 'shares', 'value': 1000},
            'raw:daily_basic.total_mv': {'label': '总市值原值', 'unit': 'CNY_wan', 'value': 12345.6789},
        },
        '20241231': {
            'rnoa': {'label': '净经营资产收益率', 'unit': 'pct', 'value': 0.15, 'formula': '新口径'},
            'fcf_articulation_diff': {'label': '校验差额', 'unit': 'residual', 'value': 1e-12},
        },
    }}
    result = history(bundle, bundle_url(bundle['ts_code']))
    assert result['years'] == ['20231231', '20241231']
    assert result['metrics']['market_cap']['values'] == [123456789, None]
    assert result['metrics']['shares']['values'] == [1000, None]
    assert result['metrics']['rnoa']['values'] == [None, 0.15]
    assert result['metrics']['rnoa']['missing_reasons'] == {'20231231': 'no_opening_balance'}
    assert result['metrics']['rnoa']['metadata_by_year']['20241231']['formula'] == '新口径'
    assert result['metrics']['fcf_articulation_diff']['values'] == [None, 1e-12]
    assert 'raw:daily_basic.total_mv' not in result['metrics']
    assert 'business-model-explorer-data/data/' in result['source_url']
    with pytest.raises(ValueError, match='expected CNY_yuan'):
        history({**bundle, 'unit': '亿元'}, '')


def test_catalog_ranks_keep_source_order_and_available_company_links(tmp_path):
    companies = {'companies': [{'ts_code': '000651.SZ', 'name': '格力电器'}, {'ts_code': '000001.SZ', 'name': '平安银行'}],
                 'unavailable': {'000001.SZ': {'reason': 'financial'}}}
    ranking = {'id': 'high_roe', 'title': '高净资产收益率', 'count': 1, 'criteria': ['每年≥15%'], 'sort': '均值降序',
               'columns': [{'key': 'roe_avg', 'unit': 'pct'}],
               'rows': [{'ts_code': '000651.SZ', 'values': {'roe_avg': 0.25}, 'trend': [0.2, None]}]}
    screens = {'unit': 'CNY_yuan', 'window': ['2023', '2024'], 'lists': [ranking]}
    stage_catalog(tmp_path, companies, screens, {'000651.SZ': ['2023', '2024']},
                  'https://example.test/business-model-explorer/', company_url, bundle_url)
    result = json.loads((tmp_path / API / 'rankings/high_roe.json').read_text())
    assert result['rows'][0]['rank'] == 1
    assert result['rows'][0]['trend'] == [0.2, None]
    assert result['rows'][0]['values'] == ranking['rows'][0]['values']
    assert '/business-model-explorer-data/api/v1/companies/000651.SZ.json' in result['rows'][0]['history_url']
    entries = json.loads((tmp_path / API / 'companies.json').read_text())['companies']
    assert entries[1]['history_url'] is None
    assert entries[1]['unavailable']['reason'] == 'financial'
    assert 'rankings/high_roe.json' in (tmp_path / 'llms.txt').read_text()
