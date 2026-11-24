import json

# 读取json文件，json.load()直接把文件转成Python字典
with open('pdd_30day_sales_over_100.json','r',encoding='utf-8') as f:
    data = json.load(f)

# data 就是json对应的python对象，可以直接操作
print(data)
print(len(data))
a=0
for i in data:
   a+=len(i['goods'] )
print(a)