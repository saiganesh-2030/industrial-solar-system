import os

files = [
    'industrial-solar-system/backend/app.py',
    'industrial-solar-system/backend/deviation_service.py',
    'industrial-solar-system/frontend/index.html',
    'industrial-solar-system/frontend/deviation.html',
    'industrial-solar-system/frontend/js/common.js',
    'industrial-solar-system/frontend/js/index.js',
    'industrial-solar-system/frontend/js/deviation.js',
    'industrial-solar-system/frontend/js/prediction.js',
    'industrial-solar-system/frontend/js/feasibility.js',
    'industrial-solar-system/frontend/js/comparison.js',
    'industrial-solar-system/frontend/js/states.js'
]

em_dash = chr(8212)
en_dash = chr(8211)
buzzwords = ['delve', 'testament', 'pivotal', 'robust', 'vibrant', 'tapestry', 'crucial', 'bolstered', 'interplay']

found = 0
for f in files:
    if os.path.exists(f):
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
            if em_dash in content:
                print(f"Found em-dash in {f}")
                found += 1
            if en_dash in content:
                print(f"Found en-dash in {f}")
                found += 1
            for b in buzzwords:
                if b in content.lower():
                    print(f"Found buzzword '{b}' in {f}")
                    found += 1

if found == 0:
    print("PASS: No em-dashes, en-dashes, or buzzwords found in any updated file.")
else:
    print(f"Total issues found: {found}")
