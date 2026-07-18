import re
src = open('main.py','r',encoding='utf-8').read()
# 找到最后一个 st.html 调用（萌宠的）
matches = list(re.finditer(r'st\.html\(\s*f"""(.*?)"""\s*\)', src, re.DOTALL))
print('found st.html calls:', len(matches))
m = matches[-1] if matches else None
if m:
    s = m.group(1)
    sm = re.search(r'<script>(.*?)</script>', s, re.DOTALL)
    if sm:
        js = sm.group(1)
        open('pet_debug.js','w',encoding='utf-8').write(js)
        print('JS length:', len(js))
        print('First 300 chars:')
        print(js[:300])
    else:
        print('no script tag found')
else:
    print('no st.html found')
