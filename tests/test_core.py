import csv
import io
import json
import math
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from dataio import read_sales, read_inventory, SALES_COLUMNS, INVENTORY_COLUMNS, csv_bytes, digest
from forecast import features, fit_ridge, forecast, metrics, blocks, calibrate, bounds, quantile
from make_demo import create
from pipeline import run
from planning import recommend, export_reviewed


class InputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        create(cls.folder.name)
        cls.sales = (Path(cls.folder.name) / 'sales.csv').read_bytes()
        cls.inventory = (Path(cls.folder.name) / 'inventory.csv').read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def modify_sales(self, change):
        rows = list(csv.DictReader(io.StringIO(self.sales.decode('utf-8-sig'))))
        return csv_bytes(change(rows), SALES_COLUMNS)

    def test_demo_shape(self):
        dates, series = read_sales(self.sales)
        self.assertEqual((len(dates), len(series)), (700, 8))
        self.assertEqual(sum(series['SKU008']), 0)

    def test_duplicate_day_rejected(self):
        with self.assertRaisesRegex(ValueError, 'trùng ngày'):
            read_sales(self.modify_sales(lambda rows: rows + [rows[0]]))

    def test_missing_day_not_silently_filled(self):
        with self.assertRaises(ValueError):
            read_sales(self.modify_sales(lambda rows: rows[:100] + rows[101:]))

    def test_negative_fraction_nan_rejected(self):
        for value in ('-1', '1.2', 'NaN', 'inf'):
            def change(rows):
                rows[0]['units'] = value
                return rows
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_sales(self.modify_sales(change))

    def test_inventory_snapshot_date_must_match(self):
        dates, series = read_sales(self.sales)
        rows = list(csv.DictReader(io.StringIO(self.inventory.decode('utf-8-sig'))))
        rows[0]['as_of'] = '2025-11-29'
        with self.assertRaises(ValueError):
            read_inventory(csv_bytes(rows, INVENTORY_COLUMNS), series, dates[-1])

    def test_protection_horizon_checked(self):
        dates, series = read_sales(self.sales)
        rows = list(csv.DictReader(io.StringIO(self.inventory.decode('utf-8-sig'))))
        rows[0].update({'lead_time_days': '20', 'review_period_days': '20'})
        with self.assertRaises(ValueError):
            read_inventory(csv_bytes(rows, INVENTORY_COLUMNS), series, dates[-1])

    def test_inventory_sku_set_must_match(self):
        dates, series = read_sales(self.sales)
        rows = list(csv.DictReader(io.StringIO(self.inventory.decode('utf-8-sig'))))[1:]
        with self.assertRaises(ValueError):
            read_inventory(csv_bytes(rows, INVENTORY_COLUMNS), series, dates[-1])

    def test_unsafe_csv_cell_escaped(self):
        self.assertIn("'=FORMULA", csv_bytes([{'x': '=FORMULA'}], ['x']).decode('utf-8-sig'))


class ForecastTests(unittest.TestCase):
    def test_weekly_baseline_recurses_on_past_week(self):
        values = list(range(7)) * 12
        self.assertEqual(forecast(values, date(2024, 1, 1), 14, 'seasonal_naive'), list(range(7)) * 2)

    def test_mean_baseline_uses_training_tail_only(self):
        values = [0] * 56 + [14] * 28
        self.assertEqual(forecast(values, date(2024, 1, 1), 3, 'mean_28'), [14] * 3)

    def test_ridge_constant_series_and_nonnegative(self):
        for model in ('ridge_1', 'ridge_10'):
            result = forecast([17] * 140, date(2024, 1, 1), 28, model)
            self.assertTrue(all(abs(value - 17) < 1e-8 for value in result))
        self.assertEqual(forecast([0] * 140, date(2024, 1, 1), 28, 'ridge_10'), [0] * 28)

    def test_training_scaler_does_not_use_external_future(self):
        past = list(range(140))
        fitted = fit_ridge(past, date(2024, 1, 1), 1)
        self.assertEqual(fitted['training_count'], 140)
        self.assertLess(max(fitted['means']), 140)

    def test_zero_denominator_wape_is_null(self):
        result = metrics([0, 0], [1, 3])
        self.assertIsNone(result['wape'])
        self.assertEqual(result['mae'], 2)

    def test_wape_and_bias_definitions(self):
        result = metrics([10, 20], [12, 16])
        self.assertAlmostEqual(result['wape'], .2)
        self.assertEqual(result['bias'], -1)

    def test_nonoverlapping_complete_horizon_blocks(self):
        self.assertEqual(blocks(420, 490), [420, 448])
        self.assertTrue(all(origin + 28 <= 490 for origin in blocks(420, 490)))

    def test_unsupported_or_nonfinite_inputs_rejected(self):
        for args in [([1] * 84, 29, 'ridge_1'), ([1] * 84, 28, 'unknown'), ([math.nan] * 84, 28, 'ridge_1')]:
            with self.subTest(args=args[1:]), self.assertRaises(ValueError):
                forecast(args[0], date(2024, 1, 1), args[1], args[2])

    def test_small_calibration_abstains(self):
        self.assertIsNone(calibrate([]))
        self.assertIsNone(bounds([1] * 28, 1, None))

    def test_quantile_small_sample_is_conservative(self):
        self.assertEqual(quantile([1, 2, 3], .9), 3)


class PlanningTests(unittest.TestCase):
    def inventory(self, **kwargs):
        return {'sku': 'A', 'lead_time_days': 7, 'review_period_days': 7,
                'stock_on_hand': 100, 'on_order': 10, 'min_order_qty': 12,
                'pack_size': 6, 'unit_cost_vnd': 1000, **kwargs}

    def bands(self):
        return [{'point': 10, 'cumulative_point': 10 * (i + 1), 'cumulative_upper': 12 * (i + 1)} for i in range(28)]

    def test_rounding_moq_and_inventory_position(self):
        result = recommend('A', self.inventory(), self.bands())
        self.assertEqual(result['target_units'], 168)
        self.assertEqual(result['inventory_position'], 110)
        self.assertEqual(result['suggested_order_units'], 60)
        self.assertEqual(result['estimated_purchase_vnd'], 60_000)

    def test_no_shortfall_no_order_even_with_moq(self):
        self.assertEqual(recommend('A', self.inventory(stock_on_hand=1000), self.bands())['suggested_order_units'], 0)

    def test_moq_applies_only_positive_orders(self):
        result = recommend('A', self.inventory(stock_on_hand=167, on_order=0, min_order_qty=20, pack_size=6), self.bands())
        self.assertEqual(result['suggested_order_units'], 24)

    def test_on_order_does_not_hide_before_lead_risk(self):
        result = recommend('A', self.inventory(stock_on_hand=0, on_order=1000), self.bands())
        self.assertEqual(result['risk'], 'point_forecast_shortage_before_lead')
        self.assertEqual(result['suggested_order_units'], 0)

    def test_zero_recent_sales_holds_purchase_suggestion(self):
        result = recommend('A', self.inventory(stock_on_hand=0, on_order=0), self.bands(), recent_sales_total=0)
        self.assertEqual(result['suggested_order_units'], 0)
        self.assertEqual(result['risk'], 'no_recent_sales_manual_review')

    def test_export_needs_human_ack(self):
        for name, note, checked in [('', 'checked', True), ('Huni', '', True), ('Huni', 'checked', False)]:
            with self.subTest(name=name, note=note), self.assertRaises(ValueError):
                export_reviewed({'recommendations': []}, name, note, checked)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        create(cls.folder.name)
        cls.sales = (Path(cls.folder.name) / 'sales.csv').read_bytes()
        cls.inventory = (Path(cls.folder.name) / 'inventory.csv').read_bytes()
        cls.report = run(cls.sales, cls.inventory)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_temporal_cutoffs_and_counts(self):
        report = self.report
        self.assertEqual(report['data']['skus'], 8)
        self.assertEqual(report['test_metrics'][report['selected_model']]['points'], 1120)
        self.assertEqual(report['calibration']['calibration_blocks'], 56)
        self.assertTrue(all(c['train_through'] < c['origin'] for c in report['selected_test_blocks']))

    def test_test_labels_do_not_select_or_calibrate_model(self):
        rows = list(csv.DictReader(io.StringIO(self.sales.decode('utf-8-sig'))))
        cutoff = self.report['protocol']['test_start']
        for row in rows:
            if row['date'] >= cutoff:
                row['units'] = str(int(row['units']) + 100)
        changed = run(csv_bytes(rows, SALES_COLUMNS), self.inventory)
        self.assertEqual(changed['selected_model'], self.report['selected_model'])
        self.assertEqual(changed['selection_metrics'], self.report['selection_metrics'])
        self.assertEqual(changed['calibration'], self.report['calibration'])
        self.assertEqual(changed['selected_test_blocks'][0]['predicted'], self.report['selected_test_blocks'][0]['predicted'])
        self.assertNotEqual(changed['test_metrics'], self.report['test_metrics'])

    def test_intervals_and_recommendations_are_finite(self):
        for sku, rows in self.report['future'].items():
            self.assertEqual(len(rows), 28)
            self.assertTrue(all(0 <= r['lower'] <= r['point'] <= r['upper'] for r in rows))
            self.assertEqual([r['cumulative_upper'] for r in rows], sorted(r['cumulative_upper'] for r in rows))
        self.assertEqual(len(self.report['recommendations']), 8)

    def test_export_binds_exact_report(self):
        raw = export_reviewed(self.report, 'Huni', 'Checked simulation assumptions', True)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()), {'replenishment-reviewed.csv', 'forecast.csv', 'report.json', 'review.json'})
            approval = json.loads(archive.read('review.json'))
            self.assertEqual(approval['report_hash'], digest(self.report))
            self.assertEqual(len(list(csv.DictReader(io.StringIO(archive.read('forecast.csv').decode('utf-8-sig'))))), 224)

    def test_inventory_change_does_not_retrain_forecast(self):
        rows = list(csv.DictReader(io.StringIO(self.inventory.decode('utf-8-sig'))))
        rows[0]['stock_on_hand'] = '100000'
        changed = run(self.sales, csv_bytes(rows, INVENTORY_COLUMNS))
        self.assertEqual(changed['future'], self.report['future'])
        self.assertNotEqual(changed['recommendations'][0]['suggested_order_units'], self.report['recommendations'][0]['suggested_order_units'])
