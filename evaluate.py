import argparse
import json
from pathlib import Path

from pipeline import run

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sales', default=str(ROOT / 'data' / 'sales.csv'))
    parser.add_argument('--inventory', default=str(ROOT / 'data' / 'inventory.csv'))
    parser.add_argument('--output', default='reports/evaluation-v1.json')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error('File đã tồn tại. Chọn --output mới để giữ lịch sử.')
    try:
        report = run(Path(args.sales).read_bytes(), Path(args.inventory).read_bytes())
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(output)
        print(json.dumps({'selected_model': report['selected_model'], 'data': report['data'],
            'test_metrics': report['test_metrics'], 'test_intervals': report['test_intervals'],
            'recommendations': len(report['recommendations'])}, ensure_ascii=False, indent=2))
        print('Report:', output)
        return 0
    except (ValueError, OSError) as error:
        print('Không hoàn tất:', str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
