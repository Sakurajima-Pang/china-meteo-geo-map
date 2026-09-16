# -*- coding: utf-8 -*-
"""内容层：一级气象地理区划归属、山脉/湖泊注记、省级要素清单、补充河流。
   依据：
   - 《中国气象地理区划手册》11 个一级气象地理区域（中国天气网等官方/授权渠道转述）
   - 中国气象局 2021《气象地理区划规范》《国家级气象服务产品地理用语业务规定》
   输出 build/out/data.json

阶段三。本文件是项目**知识的集中地**，也是三道构建门禁的所在地（文件末尾）。

数据结构要点：
- `MT` 山脉注记（键名必须与 mtn_shapes.SHAPES 一一对应，已有断言拦截）；
- `LK` 湖泊注记；`FEAT` 各省重要地理要素，河流写 `r:<id>`、湖泊写 `l:<id>`；
- `EXTRA_RIVERS` 人工补充的河流（**声明"NE 中整条缺失"必须成立**，门禁 3 校验）；
- `RIVER_LABEL` 河名标注锚点，仅对「弧长中点会落错位置」的河流显式指定；
- `REGIONS` / `WHOLE` / `SPLIT` 区划定义与成员归属。

区划成员有两种结构，**不要混用其判断方式**：
- `{p, all:1}`  整省纳入 —— 判断时用 `.get('all')`（Python）/ `!mem.all`（JS）；
- `{p, ci:[索引]}` 按地级市切分纳入 —— **没有 `all` 键**，索引指向该省 cities 数组。

新增或调整城市级归属时，SPLIT 中的城市名必须与 DataV 源数据完全一致（含「市」「自治州」
等后缀），若不匹配会直接 SystemExit 报出「城市名未匹配」。
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from mtn_shapes import SHAPES
from isles_data import AREAS, REMOVE_FROM, split_dongshat, match

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')

geo = json.load(open(os.path.join(OUT, 'geo.json'), encoding='utf-8'))

# ---------------- 山川注记注册表 ----------------
MT = {
    'changbaishan': ['长白山', 128.06, 42.00],
    'qianshan': ['千山', 123.10, 40.60],
    'yiwulvshan': ['医巫闾山', 121.60, 41.60],
    'daxinganling': ['大兴安岭', 121.50, 51.00],
    'xiaoxinganling': ['小兴安岭', 128.10, 47.97],
    'zhangguangcailing': ['张广才岭', 128.80, 44.60],
    'yanshan': ['燕山', 117.50, 40.70],
    'taihangshan': ['太行山', 113.60, 37.00],
    'luliangshan': ['吕梁山', 111.40, 37.50],
    'yinshan': ['阴山', 111.00, 41.30],
    'helanshan': ['贺兰山', 105.90, 38.60],
    'liupanshan': ['六盘山', 106.20, 35.60],
    'wuqiaoling': ['乌鞘岭', 102.90, 37.20],
    'qinling': ['秦岭', 108.00, 33.70],
    'dabashan': ['大巴山', 108.45, 31.83],
    'tianshan': ['天山', 84.00, 42.50],
    'altaishan': ['阿尔泰山', 88.50, 47.50],
    'kunlunshan': ['昆仑山', 85.00, 36.00],
    'qilianshan': ['祁连山', 98.94, 38.23],
    'aerjinshan': ['阿尔金山', 91.44, 38.57],
    'tangulashan': ['唐古拉山', 91.50, 33.10],
    'bayanhar': ['巴颜喀拉山', 97.00, 34.00],
    'gangdisishan': ['冈底斯山', 85.97, 30.78],
    'nianqingtanggula': ['念青唐古拉山', 91.01, 30.29],
    'ximalayashan': ['喜马拉雅山', 86.50, 28.50],
    'kalkunlun': ['喀喇昆仑山', 78.00, 35.50],
    'hengduanshan': ['横断山', 99.00, 29.00],
    'qionglashan': ['邛崃山', 102.80, 31.00],
    'gonggashan': ['大雪山（贡嘎山）', 101.90, 29.60],
    'mingshan': ['岷山', 103.50, 32.80],
    'emeishan': ['峨眉山', 103.33, 29.52],
    'qingchengshan': ['青城山', 103.57, 30.90],
    'wushan': ['巫山', 109.50, 31.00],
    'simianshan': ['四面山', 106.30, 28.60],
    'jinfoshan': ['金佛山', 107.10, 29.00],
    'wulingshan': ['武陵山', 109.00, 28.50],
    'wulingyuan': ['武陵源（张家界）', 110.50, 29.30],
    'xuefengshan': ['雪峰山', 110.50, 27.30],
    'luoxiaoshan': ['罗霄山', 114.00, 26.50],
    'wuyishan': ['武夷山', 117.70, 27.00],
    'daiyunshan': ['戴云山', 118.10, 25.70],
    'taimushan': ['太姥山', 120.20, 27.20],
    'nanling': ['南岭', 113.00, 25.00],
    'yunkai': ['云开大山', 111.00, 22.50],
    'wuzhishan': ['五指山', 109.50, 18.90],
    'yinggeling': ['鹦哥岭', 109.50, 19.10],
    'yushan': ['玉山', 120.96, 23.47],
    'zhongyangshanmai': ['中央山脉', 121.11, 23.67],
    'alishan': ['阿里山', 120.80, 23.50],
    'dabieshan': ['大别山', 116.00, 31.30],
    'tongbaishan': ['桐柏山', 113.30, 32.20],
    'funiu': ['伏牛山', 112.00, 33.50],
    'taishan': ['泰山', 117.10, 36.25],
    'yimengshan': ['沂蒙山', 118.10, 35.60],
    'laoshan': ['崂山', 120.60, 36.20],
    'kunyushan': ['昆嵛山', 121.75, 37.30],
    'tianmushan': ['天目山', 119.50, 30.30],
    'yandangshan': ['雁荡山', 121.00, 28.40],
    'tiantaishan': ['天台山', 121.00, 29.20],
    'moganshan': ['莫干山', 119.88, 30.60],
    'huangshan': ['黄山', 118.17, 30.13],
    'jiuhuashan': ['九华山', 117.80, 30.50],
    'tianzhushan': ['天柱山', 116.50, 30.70],
    'songshan': ['嵩山', 113.00, 34.50],
    'huashan': ['华山', 110.09, 34.48],
    'taibaishan': ['太白山', 107.80, 34.00],
    'wutaishan': ['五台山', 113.50, 39.00],
    'hengshan': ['恒山', 113.70, 39.70],
    'yuntaishan': ['云台山', 119.40, 34.70],
    'zhongshan': ['紫金山（钟山）', 118.80, 32.06],
    'maoshan': ['茅山', 119.30, 31.80],
    'sheshan': ['佘山', 121.19, 31.10],
    'jinggangshan': ['井冈山', 114.20, 26.60],
    'lushan': ['庐山', 115.98, 29.55],
    'sanqingshan': ['三清山', 118.06, 28.90],
    'hengshan2': ['衡山', 112.70, 27.25],
    'wudangshan': ['武当山', 111.00, 32.40],
    'shennongjia': ['神农架', 110.50, 31.50],
    'dahongshan': ['大洪山', 112.90, 31.50],
    'kongtongshan': ['崆峒山', 106.50, 35.50],
    'maijishan': ['麦积山', 106.00, 34.30],
    'riyueshan': ['日月山', 101.00, 36.40],
    'jishishan': ['积石山', 102.50, 35.50],
    'daloushan': ['大娄山', 106.80, 27.83],
    'wumengshan': ['乌蒙山', 104.50, 26.80],
    'miaoling': ['苗岭', 108.00, 26.30],
    'ailaoshan': ['哀牢山', 101.50, 24.00],
    'wuliangshan': ['无量山', 100.70, 24.50],
    'cangshan': ['苍山', 100.10, 25.70],
    'gaoligongshan': ['高黎贡山', 98.70, 25.80],
    'shiwandashan': ['十万大山', 108.00, 22.00],
    'damingshan': ['大明山', 108.50, 23.40],
    'maoershan': ['猫儿山', 110.40, 25.90],
    'dayaoshan': ['大瑶山', 110.30, 24.10],
    'jiulianshan': ['九连山', 114.50, 24.30],
    'luofushan': ['罗浮山', 114.10, 23.30],
    'danxiashan': ['丹霞山', 113.70, 25.00],
    'damaoshan': ['大帽山', 114.13, 22.41],
    'taipingshan': ['太平山', 114.15, 22.27],
    'dongwangyangshan': ['东望洋山', 113.55, 22.20],
}

# 校验山系范围多边形齐备，并把整数化坐标编码为扁平数组（供前端直接生成路径）
# 注意：不原地改写 MT —— 原地 append 会使模块级常量在同进程重复执行时累积追加。
miss = [k for k in MT if k not in SHAPES]
extra = [k for k in SHAPES if k not in MT]
if miss:
    raise SystemExit('缺少山系范围多边形: %s' % '、'.join(miss))
if extra:
    raise SystemExit('多余的山系范围多边形: %s' % '、'.join(extra))
POLY_ENC = {}
for _k, _v in MT.items():
    _poly = SHAPES[_k]
    if len(_poly) < 3:
        raise SystemExit('山系范围多边形顶点过少: %s' % _k)
    POLY_ENC[_k] = [int(round(x * 1000)) for xy in _poly for x in xy]

# 输出用注记表：第 4 位挂整数化范围多边形
MT_OUT = {k: [v[0], v[1], v[2], POLY_ENC[k]] for k, v in MT.items()}

LK = {
    'qinghaihu': ['青海湖', 100.20, 36.90],
    'chaerhan': ['察尔汗盐湖', 95.30, 36.80],
    'namucuo': ['纳木错', 90.60, 30.70],
    'sailimu': ['赛里木湖', 81.20, 44.60],
    'bostenhu': ['博斯腾湖', 87.00, 41.90],
    'hulunhu': ['呼伦湖', 117.50, 48.90],
    'xingkaihu': ['兴凯湖', 132.30, 45.20],
    'baiyangdian': ['白洋淀', 115.90, 38.90],
    'weishanhu': ['微山湖', 117.20, 34.60],
    'hongzehu': ['洪泽湖', 118.60, 33.30],
    'taihu': ['太湖', 120.20, 31.20],
    'chaohu': ['巢湖', 117.50, 31.60],
    'poyanghu': ['鄱阳湖', 116.30, 29.20],
    'dongtinghu': ['洞庭湖', 112.90, 29.30],
    'dianchi': ['滇池', 102.70, 24.90],
    'erhai': ['洱海', 100.20, 25.80],
    'sunmoonlake': ['日月潭', 120.92, 23.85],
}

# ---------------- 补充河流（走向为示意性简化线） ----------------
# 说明：嘉陵江、乌江、岷江下游、瓯江、钱塘江（富春江段）在 Natural Earth 中本有真实河道，
# 已在 geo.py 的 RIVER_SPEC 中登记，不再需要人工补线（早期误判为"整条缺失"）。
# 经逐条复核，NE 确实没有、必须手工给出的只有下面这一条。
EXTRA_RIVERS = {
    'nandujiang': ['南渡江', [[109450, 19220, 109750, 19500, 110000, 19740, 110330, 20030]]],
}

# ---------------- 河流名称标注锚点（经度, 纬度） ----------------
# 默认按「最长河段的累积弧长中点」定位；多段河流（如珠江）该中点会落到上游山区而非河名所指的河段，
# 故对这类河流显式指定锚点。仅需给真正落错位置的河流指定。
RIVER_LABEL = {
    # 珠江：干流名称指珠江三角洲一带，弧长中点会落到黔桂山区，显式锚定于广州—南沙段
    'zhujiang': [113.35, 23.10],
    # 长江：源数据把沱沱河—通天河—金沙江—长江作为一条河，弧长中点落在金沙江段；
    # 名称宜标在荆江段（长江中游），显式锚定
    'changjiang': [112.30, 30.32],
}

# ---------------- 一级气象地理区划 ----------------
# 名称与所辖范围文字表述依据《中国气象地理区划手册》
REGIONS = [
    ('huabei', '华北地区', '山西、河北二省，北京、天津二市和河南、山东两省黄河以北地区', '#3F7BE0', [114.2, 38.6]),
    ('dongbei', '东北地区', '辽宁、吉林和黑龙江三省', '#2FA46A', [128.0, 46.6]),
    ('neimenggu', '内蒙古地区', '内蒙古自治区', '#8A6E4B', [112.0, 43.2]),
    ('huanghuai', '黄淮地区', '黄河至淮河间所含的河南、山东、安徽、江苏四省地区', '#D9A21B', [115.2, 34.8]),
    ('jianghuai', '江淮地区', '淮河至长江间所含河南、湖北、安徽、江苏四省地区', '#8C5BD6', [116.9, 32.9]),
    ('jiangnan', '江南地区', '长江至南岭间包含的湖北、湖南、江西、浙江、安徽、江苏、上海和福建北部等地', '#2AA7D6', [114.5, 27.2]),
    ('jianghan', '江汉地区', '江淮、黄淮以西的河南、湖北其余地区', '#B25FC0', [111.6, 31.2]),
    ('huanan', '华南地区', '广东、广西、海南、台湾四省(区)和福建南部等地', '#E4762F', [110.8, 23.6]),
    ('xinan', '西南地区', '四川、重庆、贵州、云南四省(市)', '#1E9E8A', [102.8, 27.0]),
    ('xibei', '西北地区', '陕西、甘肃、宁夏、青海、新疆五省(区)', '#C2557E', [96.5, 39.5]),
    ('xizang', '西藏地区', '西藏自治区', '#6E7FD6', [88.0, 32.0]),
]

WHOLE = {
    'huabei': ['110000', '120000', '130000', '140000'],
    'dongbei': ['210000', '220000', '230000'],
    'neimenggu': ['150000'],
    'jiangnan': ['310000', '330000', '360000', '430000'],
    'huanan': ['440000', '450000', '460000', '710000', '810000', '820000'],
    'xinan': ['500000', '510000', '520000', '530000'],
    'xibei': ['610000', '620000', '630000', '640000', '650000'],
    'xizang': ['540000'],
}

SPLIT = {
    '320000': {'huanghuai': ['徐州市', '连云港市', '宿迁市'],
               'jianghuai': ['淮安市', '盐城市', '扬州市', '泰州市', '南通市'],
               'jiangnan': ['南京市', '镇江市', '常州市', '无锡市', '苏州市']},
    '340000': {'huanghuai': ['淮北市', '亳州市', '宿州市', '阜阳市', '蚌埠市'],
               'jianghuai': ['淮南市', '合肥市', '六安市', '滁州市', '安庆市'],
               'jiangnan': ['芜湖市', '马鞍山市', '铜陵市', '池州市', '宣城市', '黄山市']},
    # 山东：按《手册》"山东一省分属华北南部与黄淮北部"的表述，取南北分界（约 36°N 一线）。
    # 日照与临沂同属鲁东南沿海、纬度相邻，必须同区；两者一并归入黄淮，消除原"日照归华北、
    # 临沂归黄淮"的显性矛盾。跨区地级市按主体范围归并，与"黄河以北"的文字界线存在出入，
    # 页面已就此显式披露。
    '370000': {'huabei': ['济南市', '青岛市', '淄博市', '东营市', '烟台市', '潍坊市', '泰安市',
                          '威海市', '德州市', '聊城市', '滨州市'],
               'huanghuai': ['菏泽市', '济宁市', '枣庄市', '临沂市', '日照市']},
    '410000': {'huabei': ['安阳市', '鹤壁市', '新乡市', '焦作市', '濮阳市', '济源市'],
               'huanghuai': ['郑州市', '开封市', '洛阳市', '许昌市', '漯河市', '平顶山市',
                             '商丘市', '周口市', '驻马店市', '三门峡市'],
               'jianghuai': ['信阳市'],
               'jianghan': ['南阳市']},
    # 湖北省内三区切分：江淮取鄂东沿江带（孝感、黄冈、随州、武汉），
    # 江南取鄂东南（黄石、咸宁、鄂州），江汉取江汉平原及鄂西、鄂北。
    # 武汉（114.30°E）位于长江与汉江交汇处、被江淮三市环绕，归江淮；
    # 若归"江淮以西"的江汉，会出现"武汉在孝感以东却属西区"的方位矛盾。
    '420000': {'jianghuai': ['武汉市', '孝感市', '黄冈市', '随州市'],
               'jiangnan': ['黄石市', '咸宁市', '鄂州市'],
               'jianghan': ['襄阳市', '荆州市', '宜昌市', '荆门市', '十堰市',
                            '恩施土家族苗族自治州', '仙桃市', '潜江市', '天门市', '神农架林区']},
    '350000': {'jiangnan': ['南平市', '宁德市', '三明市'],
               'huanan': ['福州市', '厦门市', '莆田市', '泉州市', '漳州市', '龙岩市']},
}

PROV_INFO = {
    '110000': ('北京', '京', '北京'), '120000': ('天津', '津', '天津'),
    '130000': ('河北', '冀', '石家庄'), '140000': ('山西', '晋', '太原'),
    '150000': ('内蒙古', '蒙', '呼和浩特'), '210000': ('辽宁', '辽', '沈阳'),
    '220000': ('吉林', '吉', '长春'), '230000': ('黑龙江', '黑', '哈尔滨'),
    '310000': ('上海', '沪', '上海'), '320000': ('江苏', '苏', '南京'),
    '330000': ('浙江', '浙', '杭州'), '340000': ('安徽', '皖', '合肥'),
    '350000': ('福建', '闽', '福州'), '360000': ('江西', '赣', '南昌'),
    '370000': ('山东', '鲁', '济南'), '410000': ('河南', '豫', '郑州'),
    '420000': ('湖北', '鄂', '武汉'), '430000': ('湖南', '湘', '长沙'),
    '440000': ('广东', '粤', '广州'), '450000': ('广西', '桂', '南宁'),
    '460000': ('海南', '琼', '海口'), '500000': ('重庆', '渝', '重庆'),
    '510000': ('四川', '川', '成都'), '520000': ('贵州', '黔', '贵阳'),
    '530000': ('云南', '滇', '昆明'), '540000': ('西藏', '藏', '拉萨'),
    '610000': ('陕西', '陕', '西安'), '620000': ('甘肃', '甘', '兰州'),
    '630000': ('青海', '青', '西宁'), '640000': ('宁夏', '宁', '银川'),
    '650000': ('新疆', '新', '乌鲁木齐'), '710000': ('台湾', '台', '台北'),
    '810000': ('香港', '港', '—'), '820000': ('澳门', '澳', '—'),
}

# 各省重要地理要素：山脉 / 河流湖泊
FEAT = {
    '110000': (['yanshan', 'taihangshan'], ['r:sangganhe']),
    '120000': (['yanshan'], ['r:haihe']),
    '130000': (['yanshan', 'taihangshan'], ['r:haihe', 'l:baiyangdian']),
    '140000': (['taihangshan', 'luliangshan', 'wutaishan', 'hengshan'], ['r:fenhe', 'r:huanghe']),
    '150000': (['daxinganling', 'yinshan', 'helanshan'], ['r:huanghe', 'l:hulunhu']),
    '210000': (['qianshan', 'yiwulvshan', 'changbaishan'], ['r:liaohe']),
    '220000': (['changbaishan', 'zhangguangcailing'], ['r:songhuajiang', 'r:tumenjiang', 'r:yalujiang']),
    '230000': (['daxinganling', 'xiaoxinganling', 'zhangguangcailing'],
               ['r:heilongjiang', 'r:songhuajiang', 'r:wusulijiang']),
    '310000': (['sheshan'], ['r:changjiang']),
    '320000': (['yuntaishan', 'zhongshan', 'maoshan'], ['r:changjiang', 'r:huaihe', 'l:taihu', 'l:hongzehu']),
    '330000': (['tianmushan', 'yandangshan', 'tiantaishan', 'moganshan'], ['r:qiantangjiang', 'r:oujiang']),
    '340000': (['huangshan', 'jiuhuashan', 'tianzhushan', 'dabieshan'], ['r:changjiang', 'r:huaihe', 'l:chaohu']),
    '350000': (['wuyishan', 'daiyunshan', 'taimushan'], ['r:minjiang']),
    '360000': (['lushan', 'jinggangshan', 'sanqingshan', 'luoxiaoshan'], ['r:changjiang', 'r:ganjiang', 'l:poyanghu']),
    '370000': (['taishan', 'yimengshan', 'laoshan', 'kunyushan'], ['r:huanghe', 'l:weishanhu']),
    '410000': (['songshan', 'funiu', 'tongbaishan', 'taihangshan', 'dabieshan'], ['r:huanghe', 'r:huaihe']),
    '420000': (['wudangshan', 'shennongjia', 'dabieshan', 'dahongshan'], ['r:changjiang', 'r:hanjiang']),
    '430000': (['hengshan2', 'wulingyuan', 'xuefengshan', 'luoxiaoshan', 'nanling'],
               ['r:changjiang', 'r:xiangjiang', 'l:dongtinghu']),
    '440000': (['nanling', 'danxiashan', 'luofushan', 'jiulianshan', 'yunkai'], ['r:zhujiang']),
    '450000': (['maoershan', 'damingshan', 'shiwandashan', 'dayaoshan'], ['r:zhujiang']),
    '460000': (['wuzhishan', 'yinggeling'], ['r:nandujiang']),
    '500000': (['jinfoshan', 'simianshan', 'wushan'], ['r:changjiang', 'r:jialingjiang', 'r:wujiang']),
    '510000': (['gonggashan', 'qionglashan', 'mingshan', 'hengduanshan', 'emeishan', 'qingchengshan'],
               ['r:changjiang', 'r:minjiangsc', 'r:jialingjiang']),
    '520000': (['daloushan', 'wumengshan', 'miaoling'], ['r:wujiang', 'r:zhujiang']),
    '530000': (['ailaoshan', 'wuliangshan', 'cangshan', 'gaoligongshan', 'hengduanshan'],
               ['r:lancangjiang', 'r:nujiang', 'r:yuanjiang', 'r:changjiang', 'l:dianchi', 'l:erhai']),
    '540000': (['ximalayashan', 'gangdisishan', 'nianqingtanggula', 'tangulashan', 'kunlunshan'],
               ['r:yaluzangbujiang', 'r:lancangjiang', 'r:nujiang', 'l:namucuo']),
    '610000': (['qinling', 'huashan', 'taibaishan', 'dabashan'], ['r:huanghe', 'r:weihe']),
    '620000': (['qilianshan', 'kongtongshan', 'maijishan', 'wuqiaoling', 'liupanshan'],
               ['r:huanghe', 'r:weihe']),
    '630000': (['qilianshan', 'riyueshan', 'jishishan', 'bayanhar', 'tangulashan', 'kunlunshan'],
               ['r:huanghe', 'r:changjiang', 'r:lancangjiang', 'l:qinghaihu', 'l:chaerhan']),
    '640000': (['helanshan', 'liupanshan'], ['r:huanghe']),
    '650000': (['tianshan', 'altaishan', 'kunlunshan', 'kalkunlun', 'aerjinshan'],
               ['r:tarim', 'l:bostenhu', 'l:sailimu']),
    '710000': (['yushan', 'zhongyangshanmai', 'alishan'], ['l:sunmoonlake']),
    '810000': (['damaoshan', 'taipingshan'], []),
    '820000': (['dongwangyangshan'], []),
}

# 台湾省下辖（DataV 不提供市级数据，按现行区划补充主要县市点位）
EXTRA_CITIES = {
    '710000': [['台北市', 121.520, 25.030], ['新北市', 121.470, 25.010], ['桃园市', 121.300, 24.990],
               ['台中市', 120.680, 24.150], ['台南市', 120.210, 23.000], ['高雄市', 120.310, 22.630],
               ['基隆市', 121.740, 25.130], ['新竹市', 120.970, 24.800], ['嘉义市', 120.450, 23.480],
               ['宜兰县', 121.750, 24.750], ['花莲县', 121.600, 23.980], ['台东县', 121.150, 22.750],
               ['南投县', 120.680, 23.910], ['彰化县', 120.540, 24.080], ['苗栗县', 120.820, 24.560],
               ['云林县', 120.540, 23.710], ['屏东县', 120.490, 22.670], ['澎湖县', 119.570, 23.570]],
}

# ---------------- 南海诸岛符号 ----------------
# 岛礁实际面积在本图（附图约 1:2000 万）下不足 1 像素，按制图惯例以符号表示。
# 原先硬编码在前端 JS 中，现移入数据层。
#
# 结构：[名称, 经度, 纬度, 性质]   性质 'cay'=有露出陆地 / 'bank'=完全没入水下
# 后两项由 isles_data.AREAS 的声明补齐，缺声明者按既有的实心点渲染（保持原行为）。
ISLES = [
    ['西沙群岛', 112.33, 16.83],
    ['中沙群岛', 114.30, 15.50],
    ['东沙群岛', 116.72, 20.70],
    ['南沙群岛', 114.05, 10.00],
    ['黄岩岛', 117.75, 15.15],
    ['曾母暗沙', 112.28, 3.97],
]

# ---------------- 东沙群岛的「岛 / 礁」细分符号 ----------------
# 背景（完整考证见 isles_data.py）：DataV 数据把东沙群岛表示为三块按中心生成的
# 圆形 range ring，与真实海岸线无关。geo.py 已将它们从汕尾市几何中摘除 ——
# 否则主图会在南海中部画出三块实心陆地色块。
#
# 呈现在此处用**点状符号**而不是面：
#   试过面状呈现，不可读，且方法论上是错的。三条理由：
#   ① 屏幕尺寸不够。这三块的「面积」是 range ring 的圆面积，按外接框折算是
#      东沙岛 19.3×22.0 km、北卫滩 12.9×11.9 km、南卫滩 7.7×8.9 km；
#      附图比例 8.29 viewBox 单位/°，换算后分别是 1.4×1.6 / 1.0×0.9 / 0.6×0.7 px。
#      最小的一块 0.5 px，虚线样式根本画不出来（已用 deviceScaleFactor:4 截图确认）。
#   ② 方法论上不该画。那是人造图形，把它描出来就等于宣称「这就是东沙的形状」。
#   ③ 与本图既有惯例不一致。西沙/中沙/南沙/黄岩岛/曾母暗沙本来就是点状符号，
#      没有任何一处的「面积不足 1 像素」是靠画轮廓解决的。
#
# 故东沙拆成三个点，样式按性质区分 —— 这是**唯一的实质改进**：
# 既有的一个「东沙群岛」实心点会被误读为「东沙是一块陆地」，而实际上
# 东沙群岛的主体（北卫滩 −11 m、南卫滩 −58 m）完全没入水下。
DONGSHA_PTS = []
for _aid, _a in AREAS.items():
    _ln, _la = _a['coordinates']
    DONGSHA_PTS.append({
        'id': _aid,
        'n': _a['name'],
        'p': _a['parent'],
        'll': [_la, _ln],        # [lat, lng]，与 ISLES / MT / LK 一致
        'kind': _a['kind'],
        'depth': _a['depth_m'],
        'note': _a['note'],
    })

# ---------------- 组装 ----------------
prov_map = {p['ad']: p for p in geo['provinces']}
rivers = {r['id']: {'n': r['name'], 's': r['seg']} for r in geo['rivers']}
for rid, (nm, seg) in EXTRA_RIVERS.items():
    rivers[rid] = {'n': nm, 's': seg}
# 河流名称标注锚点（仅对弧长中点会落错的河流给出；其余由前端按弧长中点计算）
for rid, pos in RIVER_LABEL.items():
    if rid not in rivers:
        raise SystemExit('RIVER_LABEL 指定的河流不存在: %s' % rid)
    rivers[rid]['lp'] = pos

# 与 geo.py 一致的整数化倍数：几何坐标在 geo.json 中以「度 × SC」存储
SC = 1000.0

# 区划成员 -> 引用（避免几何重复存储）
region_members = {}
for rid, _n, _t, _c, _ in REGIONS:
    region_members[rid] = []
for rid, ads in WHOLE.items():
    for ad in ads:
        region_members[rid].append({'p': ad, 'all': 1})
for ad, groups in SPLIT.items():
    names = [c['name'] for c in geo['cities'][ad]]
    for rid, city_names in groups.items():
        idx = []
        for cn in city_names:
            if cn not in names:
                raise SystemExit('城市名未匹配: %s / %s' % (ad, cn))
            idx.append(names.index(cn))
        region_members[rid].append({'p': ad, 'ci': idx})

# 每个省级单位所属区划（含"部分"标记）
prov_regions = {}
for rid, _n, _t, _c, _ in REGIONS:
    for m in region_members[rid]:
        prov_regions.setdefault(m['p'], []).append(rid)

# 只保留省级 JSON 中实际存在的要素
FEAT_OUT = {}
for ad, (ms, ws) in FEAT.items():
    keep_m = [m for m in ms if m in MT]
    keep_w = []
    for w in ws:
        kind, kid = w.split(':', 1)
        if kind == 'r' and kid in rivers:
            keep_w.append(w)
        elif kind == 'l' and kid in LK:
            keep_w.append(w)
    FEAT_OUT[ad] = {'m': keep_m, 'w': keep_w}

# ================= 构建门禁：以下断言失败即终止构建 =================
# 这三道门禁是针对**历史上真实发生过的错误**设置的，删改前请先确认对应风险已解除：
#
# 门禁 1 —— 山脉注记落点：历史上曾有 10 座山脉的注记点落在自身示意范围之外，
#           表现为标注悬在色块外面。**易错点**：注记点须距多边形边界 ≥0.08°，
#           否则 int(round(x*1000)) 取整后可能内外翻转。
# 门禁 2 —— 省级要素归属：历史上曾把怒江列给青海。判据是要素包围盒与省包围盒相交，
#           属宽松判据（相交即可，不要求包含），目的是拦住明显的归属错配。
# 门禁 3 —— 补充河流的"整条缺失"主张：历史上曾把 NE 中本有真实河道的 6 条河流
#           误判为缺失并用手工 5 点折线替代。判据是河名的英文关键词不得出现在
#           NE 的中国河流名集合中（关键词表见 _NE_KEYWORD）。
def _flat_pts(flat):
    return [(flat[i] / SC, flat[i + 1] / SC) for i in range(0, len(flat), 2)]

def _bbox(pts):
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))

def _in_poly(pt, pts):
    x, y = pt
    n = len(pts)
    ins = False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                ins = not ins
    return ins

# 门禁 1：每座山脉的「中心注记」必须落在其自身「示意范围」内，否则标注会悬在色块之外
_outside = [v[0] for k, v in MT_OUT.items() if not _in_poly((v[1], v[2]), _flat_pts(v[3]))]
if _outside:
    raise SystemExit('山脉注记点落在自身示意范围之外: %s' % '、'.join(_outside))

# 门禁 2：省级要素清单中的每个要素，必须与该省范围（包围盒）相交
_provbb = {p['ad']: _bbox([(c / SC, d / SC) for poly in p['g'] for r in poly
                           for c, d in zip(r[0::2], r[1::2])]) for p in geo['provinces']}

def _hit(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])

_bad = []
for ad, f in FEAT_OUT.items():
    bb = _provbb[ad]
    for m in f['m']:
        if not _hit(bb, _bbox(_flat_pts(MT_OUT[m][3]))):
            _bad.append('%s 列出山脉「%s」但范围与该省无交集' % (ad, MT_OUT[m][0]))
    for w in f['w']:
        kind, kid = w.split(':', 1)
        if kind == 'l':
            if not (bb[0] <= LK[kid][1] <= bb[2] and bb[1] <= LK[kid][2] <= bb[3]):
                _bad.append('%s 列出湖泊「%s」但点位在省界外' % (ad, LK[kid][0]))
        else:
            pts = [(v / SC, w2 / SC) for s in rivers[kid]['s'] for v, w2 in zip(s[0::2], s[1::2])]
            if not _hit(bb, _bbox(pts)):
                _bad.append('%s 列出河流「%s」但河道与该省无交集' % (ad, rivers[kid]['n']))
if _bad:
    raise SystemExit('省级要素归属异常:\n  ' + '\n  '.join(_bad))

# 门禁 3：EXTRA_RIVERS 声明的"整条缺失"必须成立——该河的英文名不得存在于 NE 的中国河流集合中。
# （本条用于防止再次出现"NE 中本有真实河道却被手工线替代"的错误）
# 注：与 geo.py 一致，优先读裁剪版 ne_rivers_cn.geojson。文件缺失时**报错而非跳过** ——
# 静默跳过会让本条门禁形同虚设，而"跳过"与"通过"在构建日志里无法区分。
_NE_KEYWORD = {'nandujiang': 'Nandu'}
_nepath = next((os.path.join(HERE, '..', 'data', f) for f in
                ('ne_rivers_cn.geojson', 'ne_rivers.geojson')
                if os.path.exists(os.path.join(HERE, '..', 'data', f))), None)
if _nepath is None:
    raise SystemExit('门禁 3 无法执行：data/ 下既无 ne_rivers_cn.geojson 也无 ne_rivers.geojson。\n'
                     '  请先运行 python build/build.py --fetch 抓取河流原始数据。')
_ne = json.load(open(_nepath, encoding='utf-8'))
def _flatc(c):
    if not c:
        return
    if isinstance(c[0], (int, float)):
        yield c
        return
    for x in c:
        if x:
            yield from _flatc(x)
_necn = set()
for _f in _ne['features']:
    _g = _f['geometry']
    if not _g or not _g.get('coordinates') or _f['properties'].get('featurecla') != 'River':
        continue
    _p = list(_flatc(_g['coordinates']))
    if not _p or not all(73 <= a <= 136 and 17 <= b <= 54 for a, b in _p):
        continue
    if _f['properties'].get('name'):
        _necn.add(_f['properties']['name'])
_conflict = []
for _rid in EXTRA_RIVERS:
    _kw = _NE_KEYWORD.get(_rid)
    if _kw is None:
        _conflict.append('%s 未在 _NE_KEYWORD 中登记核对关键词' % _rid)
    elif _kw in _necn:
        _conflict.append('%s 声称缺失，但 NE 中存在要素「%s」——请改用真实河道' % (_rid, _kw))
if _conflict:
    raise SystemExit('补充河流主张不成立:\n  ' + '\n  '.join(_conflict))

data = {
    'rivers': rivers,
    'mt': MT_OUT,
    'lk': LK,
    'regions': [{'id': r[0], 'n': r[1], 't': r[2], 'c': r[3], 'pos': r[4], 'mem': region_members[r[0]]}
                for r in REGIONS],
    'provRegions': prov_regions,
    'feat': FEAT_OUT,
    'info': PROV_INFO,
    'extraCities': EXTRA_CITIES,
    'isles': ISLES,
    'dongsha': DONGSHA_PTS,
}

p = os.path.join(OUT, 'data.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
print('data.json bytes', os.path.getsize(p))
print('regions', len(data['regions']), 'mountains', len(MT), 'lakes', len(LK), 'rivers', len(rivers),
      'isles', len(ISLES), 'dongsha', len(DONGSHA_PTS))
miss = [ad for ad in prov_map if ad not in prov_regions]
print('未归入任何一级区划的省级单位:', miss)

# 门禁 4：东沙群岛的「岛 / 礁」细分声明必须齐全且自洽。
# 这条门禁的存在理由：AREAS 同时驱动 geo.py 的「摘除人造轮廓」逻辑与本处的符号
# 生成。一旦声明与数据脱钩（上游改了归属、改了形状导致匹配失效），就会表现成
# 「图上既没有区划色块、也没有岛礁符号」—— 南海中部凭空少三块，
# 而其余门禁（山脉、归属、河流）都不会察觉。故必须显式校验。
_bad = []
_seen = set()
for _a in DONGSHA_PTS:
    if _a['id'] in _seen:
        _bad.append('%s：id 重复' % _a['id'])
    _seen.add(_a['id'])
    if _a['kind'] not in ('cay', 'bank'):
        _bad.append('%s：kind 取值非法（%r）' % (_a['n'], _a['kind']))
    if _a['kind'] == 'bank' and _a['depth'] >= 0:
        _bad.append('%s：标为沉水礁（bank）但水深 %s 未在水面以下' % (_a['n'], _a['depth']))
    if _a['kind'] == 'cay' and _a['depth'] < 0:
        _bad.append('%s：标为露出岛（cay）但水深 %s 在水面以下' % (_a['n'], _a['depth']))
    if not (0 <= _a['ll'][0] <= 54 and 73 <= _a['ll'][1] <= 136):
        _bad.append('%s：坐标越出中国范围 %s' % (_a['n'], _a['ll']))
if _bad:
    raise SystemExit('东沙群岛细分符号声明不成立:\n  ' + '\n  '.join(_bad))
if len(DONGSHA_PTS) != 3:
    raise SystemExit('东沙群岛细分符号应为 3 个（东沙岛 / 北卫滩 / 南卫滩），'
                     '实得 %d 个：声明表与数据可能已脱钩' % len(DONGSHA_PTS))
# ISLES 里必须**保留**「东沙群岛」这一个条目。理由（2026-09-16 更新）：
#   · 它是该群岛在数据层的**归属记录** —— ISLES 是「南海诸岛主要岛群」的完整清单，
#     东沙是四大群岛之一，删掉会让这份清单残缺；
#   · 前端的 `ISLES_SUPERSEDED` 是按**名称**跳过渲染的。主图已整体不画东沙，
#     但在**附图**里该代表点仍需跳过（它与东沙岛点仅差 0.3 单位，同画会叠出白边），
#     渲染由 DONGSHA_PTS 的细分符号承担。删掉条目会让这条跳过规则静默失效。
# 这两份清单分处 Python 与 JS、无法共享常量，故只能在构建期按名称做一次一致性检查。
if not any(_t[0] == '东沙群岛' for _t in ISLES):
    raise SystemExit('ISLES 中缺少「东沙群岛」条目：它是群岛归属记录，'
                     '且附图依赖 ISLES_SUPERSEDED 按名称跳过该点的渲染，不可删除')
print('构建门禁: 山脉注记落点 ✓  省级要素归属 ✓  补充河流缺失主张 ✓  东沙岛礁细分 ✓')
