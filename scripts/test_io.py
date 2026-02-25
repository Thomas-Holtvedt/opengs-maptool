import os
from opengs_maptool.logic.io_module import (
    import_from_json, import_from_csv, export_to_json, export_to_csv
)

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'opengs_maptool', 'examples')
JSON_PATH = os.path.join(EXAMPLES_DIR, 'Continuous Area Data.json')
CSV_PATH = os.path.join(EXAMPLES_DIR, 'Continuous Area Data.csv')
TMP_JSON = os.path.join(EXAMPLES_DIR, 'tmp_test.json')
TMP_CSV = os.path.join(EXAMPLES_DIR, 'tmp_test.csv')

def main():
    print('Testing import_from_json...')
    json_regions = import_from_json(JSON_PATH)
    print(f'Imported {len(json_regions)} regions from JSON.')
    print(json_regions[0])

    print('\nTesting import_from_csv...')
    csv_regions = import_from_csv(CSV_PATH)
    print(f'Imported {len(csv_regions)} regions from CSV.')
    print(csv_regions[0])

    print('\nTesting export_to_json and re-import...')
    export_to_json(csv_regions, TMP_JSON)
    reimported_json = import_from_json(TMP_JSON)
    print(f'Re-imported {len(reimported_json)} regions from exported JSON.')
    print(reimported_json[0])

    print('\nTesting export_to_csv and re-import...')
    export_to_csv(json_regions, TMP_CSV)
    reimported_csv = import_from_csv(TMP_CSV)
    print(f'Re-imported {len(reimported_csv)} regions from exported CSV.')
    print(reimported_csv[0])

    # Cleanup
    os.remove(TMP_JSON)
    os.remove(TMP_CSV)

if __name__ == '__main__':
    main()