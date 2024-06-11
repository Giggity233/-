from xpinyin import Pinyin #将汉字转化为拼音
import requests
from bs4 import BeautifulSoup
import re
import csv

#将地名转化为拼音首
def city_Py(city_zw):
    city_py=Pinyin()
    city=city_py.get_initials(city_zw,"").lower()
    return city

def find_Ming_Tu(sj):
    loupan_Ming_Tu=[]
    loupan_Ming_Tu1 = sj.select("li a img")
    loupanMing=re.findall(r'alt="[^"]+',str(loupan_Ming_Tu1))
    loupanTu=re.findall(r'data-original="[^"]+',str(loupan_Ming_Tu1))
    loupan_Ming_Tu.append(loupanMing)
    loupan_Ming_Tu.append(loupanTu)
    return loupan_Ming_Tu

def find_Zhuangtai(sj):
    loupanZhuangtai1=sj.find_all("span",class_="resblock-type")
    loupanZhuangtai=re.findall(r';">[^<]+',str(loupanZhuangtai1))
    return loupanZhuangtai

def find_Wuye_Zhuangtai(sj):
    loupanWuyeZhuangtai1=sj.find_all("div",class_="resblock-name")
    loupanWuyeZhuangtai2=re.findall(r'style[^<]+',str(loupanWuyeZhuangtai1))
    loupanWuyeZhuangtai=[]
    for i in loupanWuyeZhuangtai2:
        scs=re.findall(r';">[^ ]+',i)
        loupanWuyeZhuangtai.append(scs)
    zhuangtai=[]
    wuye=[]
    for i in range(len(loupanWuyeZhuangtai)):
        if i%2==0:
            zhuangtai.append(loupanWuyeZhuangtai[i])
        else:
            wuye.append(loupanWuyeZhuangtai[i])
    loupanWuyeZhuangtai=[]
    loupanWuyeZhuangtai.append(zhuangtai)
    loupanWuyeZhuangtai.append(wuye)
    return loupanWuyeZhuangtai

def find_Weizhi(sj):
    loupanWeizhi1=sj.find_all("a", class_="resblock-location")
    loupanWeizhi=re.findall(r'</i>[^ ]+',str(loupanWeizhi1))
    return loupanWeizhi

def find_Huxing_Jianmian(sj):
    loupanHuxingJianmian1 = sj.find_all("a", class_="resblock-room")
    jishuqi=[]
    for i in range(len(loupanHuxingJianmian1)):
        aaa=str(loupanHuxingJianmian1[i]).find("户型")
        if aaa==-1:
            jishuqi.append(i)
    loupanHuxing=[]
    loupanJianmian=re.findall(r'建面[^<]+',str(loupanHuxingJianmian1))
    for i in loupanHuxingJianmian1:
        Huxing=re.findall(r'<span>[0-9][^<]+',str(i))
        loupanHuxing.append(Huxing)
    loupanHuxingJianmian=[]
    for i in jishuqi:
        loupanHuxing[i]=["信息未公开"]
        loupanJianmian.insert(i,"111信息未公开")
    loupanHuxingJianmian.append(loupanHuxing)
    loupanHuxingJianmian.append(loupanJianmian)
    return loupanHuxingJianmian

def find_Junjia(sj):
    loupanJunjia=sj.find_all("div",class_="main-price")
    loupanJunjia=re.findall(r'"number">[^<]+',str(loupanJunjia))
    return loupanJunjia

def find_Zhongjia(sj):
    loupanZhongjia=sj.find_all("div",class_="second")
    loupanZhongjia=re.findall(r'"second">[^<]+',str(loupanZhongjia))
    return  loupanZhongjia

def find_Tag(sj):
    luopanTag=sj.find_all("div",class_="resblock-tag")
    tag=[]
    for i in luopanTag:
        tag1=re.findall(r'<span>[^<]+',str(i))
        tag.append(tag1)
    return tag

city_zw=str(input())
city=city_Py(city_zw)
yeshu=int(input())
fang=city_zw+"楼盘新房详情.csv"
biao=open(fang,mode='a',encoding='utf-8',newline="")
jiabiao=csv.DictWriter(biao,fieldnames=[
    "楼盘名",
    "均价(元)",
    "总价(万元)",
    "建面",
    "户型",
    "物业",
    "位置",
    "状态",
    "优势标签",
    "预览图"
])
jiabiao.writeheader()

for i in range(1,yeshu+1):
    print(f"正在爬取第{i}页")
    url=f'https://{city}.fang.ke.com/loupan/pg{i}/'
    xy=requests.get(url)
    sj=xy.content.decode('utf-8')
    sj=BeautifulSoup(sj,"lxml")
    loupan_Ming=find_Ming_Tu(sj)[0]
    loupan_Tu=find_Ming_Tu(sj)[1]
    loupan_Zhuangtai=find_Wuye_Zhuangtai(sj)[0]
    loupan_Wuye=find_Wuye_Zhuangtai(sj)[1]
    loupan_Weizhi=find_Weizhi(sj)
    loupan_Huxing=find_Huxing_Jianmian(sj)[0]
    loupan_Jianmian=find_Huxing_Jianmian(sj)[1]
    loupan_Junjia=find_Junjia(sj)
    loupan_Zhongjia=find_Zhongjia(sj)
    luopan_Tag=find_Tag(sj)
    for j in range(len(loupan_Zhongjia)):
        Ming=loupan_Ming[j][5:len(loupan_Ming[j])-4]
        Tu=loupan_Tu[j][15:]
        Zhuangtai=loupan_Zhuangtai[j][0][3:]
        Wuye=loupan_Wuye[j][0][3:]
        Weizhi=loupan_Weizhi[j][4:len(loupan_Weizhi[j])-8]
        Huxing=loupan_Huxing[j]
        Huxing=",".join(Huxing)
        Huxing=Huxing.replace("<span>","")
        Jianmian=loupan_Jianmian[j][3:]
        Junjia=loupan_Junjia[j][9:]
        Zhongjia=loupan_Zhongjia[j][11:len(loupan_Zhongjia[j])-5]
        Ystag=luopan_Tag[j]
        Ystag=",".join(Ystag)
        Ystag=Ystag.replace("<span>","")
        zl={
            "楼盘名":Ming,
            "均价(元)":Junjia,
            "总价(万元)":Zhongjia,
            "建面":Jianmian,
            "户型":Huxing,
            "物业":Wuye,
            "位置":Weizhi,
            "状态":Zhuangtai,
            "优势标签":Ystag,
            "预览图":Tu
        }
        jiabiao.writerow(zl)















