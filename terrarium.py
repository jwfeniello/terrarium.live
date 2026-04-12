#!/usr/bin/env python3
"""
Terrarium — Fishtank LIVE Tool
Requires: pip install requests curl-cffi msgpack  |  ffmpeg in PATH
"""

import os, sys, time, subprocess, requests, urllib.parse, json, getpass
import threading, socket, queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from curl_cffi import requests as cf_requests
    from curl_cffi import CurlWsFlag
    import msgpack
    HAS_WS = True
except ImportError:
    HAS_WS = False

# ═══════════════════════════════════════════════════════════════════
# CAMERAS
# ═══════════════════════════════════════════════════════════════════

CAMERAS = {
    "1":  ("Director",     "dirc"),
    "2":  ("Dorm",         "dmrm"),
    "3":  ("Closet",       "dmcl"),
    "4":  ("Bar",          "brrr"),
    "5":  ("Kitchen",      "ktch"),
    "6":  ("Hallway",      "hwdn"),
    "7":  ("Laundry",      "jckz"),
    "8":  ("Bar PTZ",      "brpz"),
    "9":  ("Dining Room",  "dnrm"),
    "10": ("Market",       "mrke"),
    "11": ("Foyer",        "foyr"),
    "12": ("Glassroom",    "gsrm"),
    "13": ("Computer Lab", "bbcl"),
    "14": ("Arena",        "bare"),
    "15": ("Confessional", "cfsl"),
    "16": ("Corridor",     "codr"),
    "17": ("West Wing",    "hwup"),
    "18": ("East Wing",    "bkny"),
    "19": ("Jungle Room",  "br4j"),
}

SEASON       = 5
SERVERS      = list("abcdefghi")
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".terrarium_session")
CHAT_ROOMS   = ["Global", "Season Pass"]

# Base64-encoded JPEG thumbnail for offline/broken cameras
# Generate: ffmpeg -i broken.png -vf scale=320:180 -q:v 8 broken_thumb.jpg
# Then: certutil -encode broken_thumb.jpg tmp.txt
# Paste the base64 content below (line breaks are fine):
OFFLINE_THUMB_B64 = """/9j//gAQTGF2YzYyLjExLjEwMAD/2wBDAAgQEBMQExYWFhYWFhoYGhsbGxoaGhob
GxsdHR0iIiIdHR0bGx0dICAiIiUmJSMjIiMmJigoKDAwLi44ODpFRVP/xACrAAAC
AgMBAQAAAAAAAAAAAAACAQMABAUHBggBAQEBAQEBAQEAAAAAAAAAAAABAgQDBQYH
EAACAQIDBAUIBAoJAwMFAQAAAQIRAwQhMRJBUQVxYfCBkROhMgax0cFSFCJCFuHx
crKCkhXSI2IzU8I1VKJDc5Mk4mM0g0SE0yU2VaMRAQACAQMCBQMFAQEAAAAAAAAB
EQIDMRIEIUFhBXETwdFR4ZEUsULwIv/AABEIAWgCgAMBEgACEgADEgD/2gAMAwEA
AhEDEQA/AOECICGCyooMhACYhKgJyEoCcgCAnICgMgxwgMggKgMihjlAZBjhAZRi
lQGXQxSoDLoYpUBlUMUqAy6GKVAZdDFKgMmjMUqAyqGMVAZdGYhUBmUMMqAzaPgz
CKgM3ZfBmEVAZuy+DMIqAz9l8GYBUBn0fBmvKgNjsvg/A1xUBstl8H4GtKgNlsvg
/A1pUEbPZfB+BrCoqNrsvgzVFRRttl8H4GpKgNxsvg/A05UBudl8H4GmKgN1svg/
A0pUBu9l8H4GkKgjd7L4M0hUUbvZfB+BpSoDdbL4M0pUBu9l8GaQqA3ey+D8DSFQ
G72XwZoyoDd7L4M0hUBu9l8GaQqA3ey+D8DSlQG52XwZpSoDdbL4M0pUBu9l8GaU
qA3ey+DNIVAbnZfBmlKgN3svgzSGmQbqj4M0xpkG42XwZpyoDcbL4M05UBuNl8Ga
YqA3FHwZpyoDcUfA05UBt9l8DUFQG1o+BqioDa0fBmrKgNlR8DWlQGxozWlQGyoz
WlQGxoa4qAzqGCVAZxglAZ1DACAzaGEVAZlDCKgMsxCgMoxQAyTFCAyjEKgMkxSo
DJMYqAyTGKgMgxyoCchKgJiNa9wAEUAKUKBPVj4kUAjIoBoERQASEURGJhFBEdSg
JCOrACUizIAlIqMKCUioRQSkdCKIkqgNkiqg6oHZIqoKqFskVUPaRdkiqhbQeyiK
ANok2URVRHtEuyiKqIdom2URVRDtE9CKqINoyaEVUY20ZVCKqMSrMqhFVGLVmbQi
qjCqzNoRQYWZm0IoMLMzaEUGF9Yz6BQYGZn0MtKjBozPoZaVGBSRsKEUGvpI2FDL
QNfSRsaGWlRr6SNhQig1+zI2FCKDX7LNjQig12zI2NKGWga/ZkZ9KmWlRgbMjZUM
tA1uzI2VDLSo1uzI2VDLSo1mzI2VNDLSo12zI2SWhloGt2ZGxoZaBrtmRsSKrLXb
MjY0MtNI1uzI2NEZaVGupI2NDLQNbSRs6EUGspLrNiZaBrvrGxp26jLSo131jZGW
lRrMzZUMtKjW5mzoZaVGsqzY0MqqNdVmfQjSowKs2CiuBFBgbRnbKMtKjB2jN2UZ
aVGFtGVsrgZaVGLtGVsLgZaVGLtGTsIyqox9on2ERVRBtIl2CKqIqoPYIqoCqHsE
VUKqLskVUOoGyRVQZHssiqJCKjIoJCPMgCQiCgkI6kASBIABoShQBQIigRSKBrXu
ZVr3MgBjABFKIq72XiRQUYAIIABCAgx5FlqQUIIAKEACCKgEGVACSFEUBIERQEhU
RQE9Coio6EtCiKioTUAghoZKQAY9DKpoAVjGTQCKgpUy6cQiKxaGZs8SoisWhm0R
WBWLsGaqVS1zpp0GmEabDBctu42ajBUj9qb0j731HcLEY2oKMUkqLRUJOVONYxt1
Oa3/AFdv241t3I3s4rZo4vPV5uiSfmzOtKR18nI5uLpce+7+L2XnaTrptPjro8t6
OwSklFvgm/BHXycjm4uh8yuNO72mxaWb9p9FlxNNds/hNjSppGVa7ZNko1W72+cq
IrW0Ztdj2denRuqURWr2Ta7K7cCoitYom0UOjPcujUqIrV7Jt9no350KIrU7NDab
NctKrpYEGrcX0G32ElXfl2QBWo2czcuPdSnt7MCDUuL07d5tvJ79+Xm6woNQoVNw
4que6nBaoig02yzbbNfcyKDVbPmzZuFDRcV7CKDVbHebjY06a9qEUGmpn7jbqGiy
4pkUGm2e3SbdRS8xFBrNnJm48nlxS7ZJfEig02zmjb7CpTXo/GRQabZ4Z5m12aU+
Hw4EUVqthm5cNe7LtnqRUVptnt0G22M2tK+PWRUGo2d6Nqo5b9euvx0IoNTs+7I3
Own1b9SKDTUZt9nXKhFBp9k3Hk6LXRd7IorU7BttlV0os8yCK10LM7tyEIR2pSdI
ri+Cqb7CfwsTh58L0FXLTapQjOWwsbtbLA4mFW7N1UpWsHk5abt+4+n6DlDhKl1v
l+3gsRclsqzcbrs02XlKlaOuSdOJ9Q018/X0nbbictOl8y3uWYrDw8pctOMcs21v
3UrWp3jm8NvA3lStFGXhJM7YyiXPjvDmqXtOz5u2GbXZ3vLqOxXMrU7LNko6biKg
1uyzY7PXpmFQa/YNsodT3EaBp3E3Lt9XXQy0I0lDbOBlpUaehsnD4dxlpUayhmuF
KmVVGuaMxxMtNMsGhl7Jlpplg0MloyrSMQyGiKqMUmoZVUY5LQiqIQyKCIkIAhYT
AocSw1ACcYAAEAABAAC17mNel3MgBlACiKIHx6R8ekgooygKMCCjADDepd5BQYwo
DCAAQwAQZFAg6EAImoAA0JEAAknZAAJJ+EAFSpNSmvZgACj2/GS03dvYACpqMAB6
MzZ4OzG/irNqWalJJ9AQGuWh3u3yzCW81Zt96r7alQacG1ruXSfSMcPYX+lb/Uj7
gMtPmrd8T6Zdm3/Vw/Vj7iCK+cLSUpwWWcl7aH0HetQ2PRivrR0SW9EknaSFjdAk
0TrM4FdYSGAGPf2pWbigqtwkkt7bRmQ9OPSWN4XHeEnZJ2cfjynHun8Cfe4rdTez
vh3DkVwlckx7p/B6W5w/eO9IqIriH7Cx7p9S2t7rcX4Tt5URXGlyDHNUrZX6XuR2
ZFRFciXq7i3rOx+tL9w7GVEVyFereJp/S2P8/wC6diNMstORL1bxO+/Z8J+47EaZ
ZVyL7tX8v49nLqn7jr5plFcg+7WIr/T2d26fuOxGmUVx/wC7WI/rrPhP3HYTVsor
j33axK/17PhP3HYzVog5BH1bv5Vv2uvKXuOvltAcj+7d7dfteEjrxq2Qcd+7N/8A
xFr9WXmOyUNWyDj/AN2sR/X2fCZ2E1bIOPfdrEf19n9WVfZwOxGrZBxz7tX/AOut
ZaZT9x2Q1bIONP1axH9dZ8J+47KatkHHF6tYiv8AT2qdEvcdjNWyDjT9W8Tuu2Mt
PT9x2Y1bIOJP1bxdP6Sx4zX9k7aatAcOfq5jNNux+tL907WW2QcU+7mM3Ts/rS/d
O2mrQHDfu3jfms5aUm/3DuhUBwx+r2O/8NPy/wDtO5FQHCH6v4+no2n/AO4vid4K
grgT5DzBf6cXTT68PjI76VEV853eS8xi4y8kvqyTynDdnX0j6HnGqJKiNQsyw9GP
QjhV1oYVDKqjXYm35axdhktuElV6ZrUz6VRY3QlXMI+rF+XpYi0vyYyfuOzRzSO+
2HIrka9V3vxK6Fa98zrxq2UHKo+rFta4ib/QivizqRq2RXMJ+rdqMZNXrlUnT6sT
pzVTdsMq+WpRo2nTXfvp0G5xVryeJux+W7Oi1yq2ewwNIomXRebNcOjr6CgNbKPs
0Mhpa6vtuADXSjXqMxx1r+IANe4195k7L8xFBgbOu4ydmu73V6yAMBqlegyGvO+4
igwXEyGiAMEyGtxFUYdCZogDFoGyCiEIigx2EyCoCGpYekgKMsIAIwgIAGBURr0u
4f2u4goZQAEpRAXHpHx6QKGMAhjACjADXrUa1IKJAkVASjKIKEBUMIAphAAxoiiC
GRQNewPUiqgk9All0/AiqKkiTtTgRQBn1llkte24igCuRgSbqRRHquUyT5hhkvn/
ALLIOS/3jhvypfmSMq0j6LEyDQNEYASg1ADEuukdG89Eq5GSZnvDSxujTxktz7d5
vNlPdU4amPB3uq4crVo2yhH5UfOfQp2ORhW19ePbcbOMVHRHHjvDsp0ZbOZKilAE
FQgACQAEhoAJSgAQ0ABFACRFQVBIhgAxgEUICoZQoqlIqKIpFQIZFAxgFUQEBFAC
lABlAAGIAEMCoYgAoSAChAAIQAIIAAYYAeeipqOdt/VbWT3LRr4noDnnGXQ9oyeL
StNKtHTjTszeHLxl0ui4c7QUk1VRbT3noDl4y6nTcOZg201FV1MwzHaGmpRCSAER
UDIqoiDIA4DzJf8AW4j8vr7dxJzX6uOxPXJfmo9YIZHn9ab2lXXf1EvU6ZvoSfs7
iiDCcd6rV9X4TJefetO24qA1zWayeffkjKcaUyplv3/hKgNa1puXahkUXRTNvf3f
AAMF613ZomaWdH4dYAYjXVu3kjy/EAGG12+JJJL4dqgBjDfsIAxmu2RKyCjDDYAY
7JGiCjDYbIAx16S6Rb+8iqNgEwAjGBFAMAI/tdxftdxAFEACGUQFx6R8ekCgigAw
gAT0fQWXovoAgwIjiRVEyGgCJhgAxgAQ1uAAqDQAEl+IJAA+/oVQ13AVFp2oGtev
zduIAFqukNZeHDvAC8N/R2zCWXDrACCWm7Ms9AA1jCYAel5Gq8ysfp/mSD5F/eVn
9P8AMkBR9CaFMjQIoAKgWgUFQRFAaKggJUVABLQoAUCco21KUmoxiqtvRJasAidH
IZesOJxd7yXL8Pt/zTTbaX2qViorpZRUdfOPz57zHAXIxx2Fjsy0cfqt8dl7Uotr
gBUdhR5fFcyjHl0sbh9mf1YuO1WmclFqSTTqt6Iqo9YeF5FzW9zON53Ywj5NwS2K
/aT1q3wAD3qOb895xf5XcswtQtyU4Sk9tSejplSSIqo6BfvW8NblduvZhBVk6N0W
miqzlvN8Xj73L4SjZg7F7DwnenvhKTTpFbVaabmRRHRcHzDC4/b+j3NvYptfVlGl
dPSS4HC+RXeY2vLfQ7MLqbh5Tafo60+3Hr4gVH0ogUFUEanH4+zy+xK9drRZRivS
lJ6RXbJEURtkzjNnnHOeZOUsHhrcbcXSrVe7anKKb6EQVHazkGG9Y71i/wDR+Y2V
adUnOKa2a6OUW3WP80WVAdRxOItYSzO9dlSEFV731JLe28kcs9ZruNdudvyMfolb
T8rX621rT0tK5eiVAZUfWyzcuKEcNedZKKe1He6Voq+08z6v3eYW4Uw2Gt3LUrq8
pcfpL0aqu2tFmsmVAd/KUAzzHNOaWeV21Kac5zqoW1rKmrb3Jb2AHpTjtrm/O8XH
ytjB23b3fVbr0OU4uX6KCA7Ic15Z6wxxV1YfEW/IXW9mOuzKS+y0/rRlwTqVAdMO
Zc655e5Zfhat2rc1K2ptz2q+k1RUa4FAdMOPP1jxWJvKODwjnbUoxlNwnOuaq/q0
UVwrVgB185pzb1hjgbrsWLau3Y+k5N7MW/s0WcpeAQHQ7k1bhOb0jFydNaJVOST5
xzOFmbxmBcbM4Sj5SMZRcdpNJtNyyz30KgPZ8u51h+Z3JW7UbsXGO39dRSpWm6T4
nL/VOqxl3/Yf58SoD6BOdcw9YIYa99Hw9p4i8nsujeypfLkm5S4pFAdGOST57zLC
0nisBsW29VtR7qvaVep0CA64eet8xtX8FPF2frKEJy2Xk1KCq4S1o/xlAejOPWvW
yMrdx3MPSa2VbhGTe23WtW45JZca1CA7EeT5Rj7+Pt3JXrPkdmSUVSaqmq1+tr3F
AesGACGAFKACEQAigADKAADIoOHc5Wzj7mWsYS6sortvM3ny2cXXjaj7WvgekJDK
vHVXTrXWlVpwpUCNJU3L2s0IKk96q66lVKLNZeOXj8QIqFrc3vzz3fAtKUe7f2zA
ggdWq0ej46dyXiVqmumT89AAx288tVovwhdYAYz16/GvUE+HgggMN9nxz9hK8t2f
aoBWG/aG69eoAYrJH8SAMNolYAYrCZBRhsbICsV6llqAGyKUAAyAIxgBF9ruH9ru
+BACGAAlKIDW/pHx6SCghlAMYEAS9Fln6LAKw4liAE6GgIJkMAGMADFWgASr8YkA
E2o15goKvdxD6URQXjvYfxZFBUujrC8/V5wAa68uvtQe9eIAQT08w5+IAaphsgD0
3IsuZWP0/wAyQHJP7ysdM/zJAUfRTEQaBIQATUqVAQLQMCoYgKgtCphFEqEigjzf
Oozny7EqFa7FcuCknLzVPUagBxb1TlbU8TB025KDjxcVWtOhtVPQ4n1ZsXLnlMPd
nhpVrSKrFP8AlzjKPQnQCBetMrawUISptu7FwW+iT2n0biG36rxnPbxWKu3+rSq4
OUpSdOigAeewkJ/dzFt1o7jcehSgn50ztTwtl2Po+xHyWxsbCyWzTTtvCiuUeqM4
/wDVQqtp+TklvaW0m+4kl6pqNytrFzhHdWFZLq2lJewioNR62XYSxViEWm4WntJb
tqWVT00/VPDzjDZv3IyVdubSk5t79VSnURQbDE//AK7/APS2v7J62OBt/Q1g51nD
yStN6NpKlep7wCubep+mL6bX9oyo+qcbc9q3jLsVX5VWnCsZL2EEHYRIoK5J63wm
7GGkvQjckpdTcVs+xnUr9m3ibcrV2KnCSo4vt4MCK8b6tXLc+W24xa2oSmprepOT
dX0qlDRT9VVCblhsZdsJ7qVdOG1GUG10hEHmfWyduWMtqLTlGzSfVWTaT66e091g
fVrDYa4rt2c8TNOq2lSNeLVW5PpYUGPzWM48ggp+lGGH2q61rHU9xzDBR5hhp4eU
3BTcXtJJtbMk9H0EUV4j1SdcHe/3/wCxE9ZyrlkeVWp243JXdue3WSSpklTLoAg9
OMAOBetsZrFWZP0HZpHhVSe17UdlxuBscwteSvRqtU1lKL4xe72EUA8tnbuYLDO3
Rx8lBKm6kUmulPU50vVi/Z2o2OYXLdt6xpJeOxNJ+AQHiebtXOc3PI5yd20ls/1l
Ip/5vOdb5byDDcvn5VyleurSUkko13xjnn1tthQc79bl/wBXZ/2P7cjofNuRx5rc
t3HedpwhsUUFKuda+kiAPR8uhG1g8NGCUY+Stui64pt9LepsLFvyNq3brXYhGFeO
ykqlAfN9pq1zyt/KmLltbWlXJ7LfVVpnXua8hs8xl5VSdm7SjkltRmlptRy04pkU
HqMbsLC4jytNjyU9qulNl9kc1t+rWIlswxOOncsxa/hx26Om760ml4dAQHmPVT/1
01/4JfnQOgcq5D+zMRK95fylYOGzsbOrTrXafAKDkGAWJXMFGzOFu+53EpXKUUs6
rOMs3mllqdi5l6v2cbcd63N2Lrzk0qxk/maqmpdaZFBpcVg+eXbE4YjFYTyTX19r
Zitfm8kqZ6Zgy9XuYYhKGI5g521u/iS80mlXpIAfK8HcwuD5jF3sPdjKy2lZubey
9ieuWVV7D32G5bZwmFnh7VVtxkpTecpSlGm09NNy0Cg4/wCqtqE8ZclKKbt2qwru
bklVddN50Hk/I5cruzuO8ru1DYooONM06+k+BFB0IoAMEAKysAKCABAMgKMiqBFM
QEUDK2BFcg9YY/x7b42vZJ+8n9Yv6Sw6fYnn3o3BDJLwPxp1uvjkQLNVrk6+40IJ
HTN0ao14voy0LV0zprrxXcAEb661fsXmoA6rxz6u9gAGueXty07ZFa4V9uvDgEBj
tcV178+3cG+PRRunbeAEGvWteGfR5iyyqvO+2gAQPLzrfn0FeXD2gBjfiCe/d0cf
gQBjMkpu7fAAMRoN+cIoxWN+cAMNhMgDClqOQFRsuA1ouhFFAhABCEQEQfa7vgP7
Xd8CChFAASlEVJx6Rrf0sgAkEVAEMoiop+ixXPRADEiWIATIJAETjRQDKAEi9glm
AEowAaRfgAEpV4gAfFrIHN9/EAD0YaffpUALTuCyyrnqFBjXN/4Sz0p49qEAa0ZA
HpeR/wB42P0/zJBcj/vKx+n+ZIiqPoUkINAUGgCDQSAChgBdRoKCMkoRQMGhFBOC
iKCQoBEgKAoJDQBF1DAoNDABjAAkUAhlAqKMCijABlAAwQIoygQEDUAGUCoIoAIo
BSEBFMoEDBAKMjAgkBABhAVDGAFKAFqIACKAFEAFEACKQUAMAFUB0CAZGVBTYgIO
V+saTeHfVc/s9kTesUaqw1rWaXfsm4IQcx3ZUWnXu35FyXCle2VTaMgnvWeVOALd
Oqnbq4+IAWj6N2VGKlFXenV61ABVrpklu17+8F9yXnfHvACN0UWs+OTTK3406sgA
x3Tqz3aU+JXVV19/QAAe8i0rTPuyCAj7fhCb4786dwAYr7bwtMgAx6ceA326kRVG
OwnwIAwmJkAYkhzADZL0V0IsfRj0IoorKRQRDIIqD7Xd8B/b7vgQAIwIoSlEVIt/
Sx8elgARQAMoEEVz0e8tz0e8AMSJYgUToqAgySooA/cVAAfuLxACQvEADWfXqEuz
7gAPdv3dugap0dfeADfszGsvHtxKAqq9Msh03a/gAB1rnr07vOFq/b8AAx7gpqnj
27Mig1zCZkB6Tkf95Yf9P8yQHJv7xw/TL8xgUfR2pEQaEgqgAZUBFS1BAgOpUUAQ
gCCKgKg0ICh6DoABCACVCQEVMICAzxd/mjnd+jYCCxV/Padf4VrruS07kBUekxeM
s4Gy7t6VIrJJZyk90Yre2anDclpchiMbdli8RHONcrNp/wDjh1cX4AAWE5rbxN3y
E7V7D3dnbVu9HZco8YuuZk805dLGeSu2bnkcTYbdqesXXWM8vRYQHoTwsbnPZ0j9
Fwltr0pzuuUZfkxhmu8oqPdnivJc9pteVwFfk2LtOjaAqPa1PCSjzzEfUphcKm/r
XYSlcml/LFqlekCo98eI/YMZf0uNx12vpfxtlS6tlLJAB7g8b93eX0yV+L4q/dr0
+kEB7Q8H+zuZYXPC47ysf6rFrb8LkfrFAe8PCvl/M8SqYjHq3F+lDDW9nLgrj+t5
gA9NiMbhsGq371u31Sln3R1fgYeG5NgcK9qNmMp/1lytyfTWdad1AA0scZzHmVXg
7UcNZ3X8RFuc+uFrh1yOhgByjmmFvYHB3cTd5li53IpK2ouNqDm3ktiKz8dCTE7G
K57CziF9SzYU7MJejcuN1c0tG4r80gD32Hc3ZteU9PYht/lbKr5zLRQDGAUhARRg
ARUgAEBiAAhAAYgAIQAMoAUEAKwQCqKhAANhUAqIcyQgqIRgUIVSoDnfrEv4NiXC
curWP4Cb1iX/AEkP91eeMjcJDMjkKe7rrxy8AE+FXu2V1HojIlo9++lH2QFaU6s9
/UUAsuKeeb3e0FtKmennr1kAV1zrlrl0Oomt+r1p58+GQAC8vDTd7St0XnS19gAR
vf5kuG/qAa145PfXr1ACN592i8OkdN+ST1fm6iAIunPh7wXl7AAx2/xdvON0047g
Age/oLvIKIn2RWAGHLUUiAMOQ5AUbCHox6Bw9BdAAEUAIygEQ/b7vgX7b6PgQUIo
AAUogl49LGt/SyCgilEBjACC56PeW56PeAGLEUQKidDQATjRQEiKkAB+coASreIA
DWY15goD7aF6dPw7gAPV9qULp1AAa3V/AvjUvHPXtoAFp3fEfB9LACCeiLOm7pIo
NawmZAbzlH944b8p/msHlP8AeGF/3F7CKo+jUSUINCoMAGFQADCSKiAQ6FEVSQCK
QQEVS1oAEiPEvHYrHzla5dbi4xbjPFXf6KMt6glnNrwAg3uM5hhsDs+WnSU/RhFO
U5dEY5kuA5Rawc/LzlLEYmS+teuZvrUFpFecIDRLH4zFvZweCuaVd3FJ2YLoWsn0
HTKgBztclxOJrLG4266/6WHfkrSXD5pdJ0QANbhMJYwVtWrFtW4rhq3xk9W+tmcU
BK2CAVSgECEBUAEACKAFGAFRQAYwAEIAKIAJAAA81zPlseYQg1N2b1mW1ZvJZxfB
8Yvej0wAc9eN5lgkvpWD8vFZO7hZbTf8ztNJqp0IAPLYTmuExrcbdyk1rbuJ25r9
GVPNUzcXy7CY3O/ZhcaVFJ5S/WVGAVtlmeJ+7uB+z9Ih1Qv3EvawiD3FDw75J5L6
2FxmLw8t9Z+Wi+mNz3lFR7c8O7XPbXo3sFiPy4Ttv/LkAHuTwn7Sx+GdMVy+bj/W
YaXll+r6SAD3R4j7wYRf0lvFWeu5YmkulqoAe6PEz5/gVRWpyxM5ejbsQlOT6cls
94Ae2PC//mMbutcutvj/ABb9PzIvzgB7ac4W1WUowXGTUV5zycOR4Vy28Q7mNn82
IltJdEVSKADJu865faez5ZXZfLZTuy/yJrznoLNizh1S1at21/JGMfYgA8hG9zLm
DrYj9Bs7rl+G1en+TbbpFflHvCKDwtq9i8JjrWFxF2GIhfhclC4ratzi7ebUlF7L
TW8hw21jeaYm9PKOD/6e1FcZKs5vrehAHuigUCUAImhkFEYYAeB9YK/RI0y/ix/N
kF6wr/ol/uw69UzUEMjiq8K56508N4CpRZKq7vFmxkSrpyb6699PcDVrTOlHuQAJ
yosq667vBidOGj6fYACyz8dejpAyT69/Rv1AAO5b1QNuqddz7buoAIm6JqvV3fET
eu7TTu1ACPVV7Lza55BNcc6+bpIAib8H1APPXt4ABG8tRN7Pb4AAEt4PuIqiF/hF
3kAYktRSIAxZlluAqNhD0I9BbfoLtvAoIQAAUAiD7b6PgP7b6PgQUIQACMoIlW/p
ZVv6WBQYwICKAEFz0e8tz0e8AMSJYgFToqAgygSgJK+wYAGuoWu8AJkJcAoJekSf
mAAx6b6gAS3j1y/B5gAPRv25dAlThrn+IAGlTv7btC+3gtN2oUEEnX2FnnvIA1zK
zIDactezjsL/AL0PziHBOmMw3+9b/ORFUfT7CINBIYATVBCiDKRQGDUAJ6CQAMoE
V4S7K9zm9cwthu3hrUtnEXlrN77Vv4sy/VmcY4a7YeV21iLvlIvXN5PjTd3AQdAw
9i1hrcbVqCtwgqKK7Zt73vMoigIjqABVAIqoOogAMEACKAFEADEADEADZdQAqKAD
BqABCAAgQAIoAUQAMQAMoFRSgAygAxgANAgAAOgFRG1UIAMaFq3bbcIQg5ek4xUW
+lpZmSBUMQAIMAEUAI7lyNq3OcvRhFyfRFVZ4z1hutYF2Y+niZwsxS1e1JbXm1CA
j5FGc8PcxU8njL079OEXlHzI9hCMbcIwiqKMVFdCVEBRORgAQAAURFVCFUiivFc/
TeBdN1yHtZNz3+77vU4P/MiwQyODad9cty4PcWNaZ7nu9vWbGRVpwq8wdnr66/DP
3gAq9WVX0ib16n2ebAAvRr37s0DRZqlevdTLfQAA146PMLXoWT8egAA3+2vRpSug
Ly4JZZd3TUAIm+9rzdINGqrz9JAEetV+Ikefs6PYAVDp1lz7e8CKgfnCeXcQBC2D
27bgAxZIUiAMWZZgFZ8PQXbeWHoLtvAAygRUZQIIftvo+Bftvo+BBQihQIoEEnHp
YuPSwKJBAQGUKCG56PeW76PeQBiRLEAqdCQEGWIoAxoACEAEvuKUBKuyoJABKLzd
YAFXWuvb4j6QAvEKnXu01CgLJdWmWY69t9O28AMade3AKW7h26iANaNmQEmHeziL
L4XYP/MjHT2ZxfCSfgwCvrR6jqQaCGFQEhUAAigAxkUBggBMigBocTyvCYqflJQl
G5p5S3OVub6XFqveb8CK8W+UTtNvDY3FWG1mnLysW+LUz22oEHkUudw0vYK71zt3
IP8Ayuhub2Nw2G/pb9qFPmmq+Fa+YiitRXnc9bmBt9Shcl31bRH+3cE/6Py19/8A
is3JedpIioJPI85X1ljcPJ/I8PSPintEMuaYm79TDYDFSuaVvQ8lbjXfJtgBleV5
4v8ATwD/AErqFDlvMbi2r3MbkJvNwsW4K3HqW0qvpYAB5DnF+rnjLOGr9iza29lf
lzo6k/7Kxn/9TE7P5Fra73QAPNcxs4jlVj6RDmOKnc2oxjC64zjck36OzTpeR63D
8lw9q7G9dnexV2LrGd+e1svjGOUV5wCvXw2tmO1lLZW11OmfnJQIKUAoSgAVQAIo
xAARQIp1EBFEICKogIplAimICKZQIplAgYgAkEABAgAwQAoWoADQWgAECEAR4Lm+
JvynawGGexdxKk5Xf6u0spNfzPRFQGDbmuac28rH61jAxlCMvszvy1px2Vv6j12D
wlrA2IWLSpGC75PfJ9bAK2owAEoAAUAECAFEBUeR57/d979D8+JPziNcBiOqKl4S
TLBAj5+XVm+HcRR/DRZ+/d4GxlUteqtOgWSXU3Xr9gEUm6dMesteC38X0gQC1SvT
lu/EDTv1dXk34sAK9HvzzXiBlrVaZgA6rTx+G4CqXmzrn3+AALdv06wH7SAE865b
ivjSnECgG123ETy0AAXxKyAImWoAYkiy1IAxJimAVn2/QRbfoLtvAAigRQFACH7T
6PgP7T6PgQAJQARSiA1v6WVb+lgUGICCQQARXPR7y3PRADDiWIBU6EgIMspQBloV
AGhoqANFQASCWZQBrsx16+AAHomy7+jiAB9kP3dukKBZ+bNjze/4ZkUGNLt0hz6y
ANexvMyAxWxyAo+srctqEHxjF+KRr8FLaw1h8bVv8xEVpG2GQUNDQEEiGVAUkKAj
DADzOK5krFxYezanicQ1XycMlFcbknlFGs5F/FuY/EpZXsQ1Cb1lGHnogCM5Ybmu
IzuYmzhU/sWbe3JdW3PKvQe2TADyH7DtXP6fEYvEdU7rjHwhsntAoPP4flGAw2cM
Nbr80lty8Z7TPRpkUCSppl0Gtx0L1zDXI2HSbWXF8UnubWhHnnfGa3Hf02WnjrYT
qReN9/u2yafWcG5fipYHEqU9tR0uRzrnvcXq1qej4uGU4Zd783C/p/VaGPVaNY8Z
nfGfpfm76av6bh1b8p5a3sJVrtLTo17j7Tz541dw/l7s/j63Lh8eXLaq/wChtTlO
J53dvXI28J9VOSSk1nN14PRec9HzctaZmsXG/b6Pp2GnhOev3qJmo2j7y6pQO3tb
K2qbVFWmld9Oo+kkPxLWVXPG68L3oBklGUQVqG0BUKggCqEAQAwKGIAGIAGUAEEA
QhgUUYAAVgAQqAARUADPLY3m1rCXI2YQniL8s1ZtUckuMn9ldIQHq6nPvp3N19d8
ut7PyRxC8qvFbPcVEV0A8G+a455rld+i1rctqXdHeVEHvTxNjnmHuXFZvRu4S49I
347Cl0S9EqA9rUEqCqKoAc+5x/AxnLcSsn5b6PLhsXFv79DI9YbM7uAc7abnYuQv
JLP0Hnl1J17gCPZGBhcTDF2Ld6DrGca9+9dzyAo2QAAGIAEMAI6EoAQ0JQA0ePjt
4TELjan5otmyuLbjKPGLXiiiD5Vi6rPThwz6ak1KSe7NqvR1GxlQV2aV3duI1vfX
Thv60wIFs6Vzpr494Lpnmn28WAC9jr1dBdauvs6NUAEXRlu4FfbswATbfVu7cUC8
8+7oIAH4ZV6xvfmAET6a9syt7s/xgUDXtxBpl23ABC6hPtvIAh+A3vADEkWRAGJI
sgKjYW/QQoeigKDZWAEZQCIvtPoL9p9BBQhMAKUogLe+ll49LAokBAijKBBFc9Ec
/RYAYSKgKidCQAZaBRQEmosgAlEABrISqFBMCvaAEq03UEvYAEuum/w3A9kAEi6N
aCT6twUBdIqrJvtUgCKWWvWDLPcAGFITMqCFlZAH0vyuW1gMK/8AxR82RhcllXl2
H6oyXhORFaHrQQgJECAGQmAmUBKJBRBiqRVRz1K9yK5dnC3K9grkttqL+vh2/SdH
rA6M0muJFANi9bxFuN23JShNVi128UeGlgsTy2bvcv8Ar2m63MJJ5Pi7LfovqCA6
QeewHM8Pj1SEtm4vSszyuQa1rH4oqA9EhlQE5FtbKbe5V8ADURcxH5eV5xhrF6xK
5cahK2vqzpm/5Hxru4HOcZjL/Nb0IQi0q/Utre/mk+PmSOXVxxmLntThyznUmo/Z
9zoNfV09WMMY5Rlvj9fKn63p+n0+i05yyyi/9ZT/AFDyh0fDer9x7Xl5qOX1VB1e
1xeVKLhvOV346E+L7b8lreqYxXxROXfvyiu3kxOQwtPEOcpxUor6kHq296rvXVnm
aLFYHEcumnLStYXY6VWnQ+pmNGI5b+0PLLCcJ+ro9Ty1I0oxxxnjM/8ArKPCvCX0
dDqdLqsZiN6rLCd/1fQpzzl/PPpE7dm7bpOWW3F/Vb6N1T7bhw1uUxEw/lr9X1Xp
3xY5amGV4x34zvEe7pFSOp3D8oLUFsAKCgCiGBAI6AAh0ABiAClAqKUCghgQIryA
qMK9ft4eDuXZxtwjrKTokcxwNj9uXJY3FPatQuSjh8P9iKi/SmvtS6fYQVG+XPJX
6/Q8FiMTFOnlPq24P8lyza7j2iSSolRLRLcUFeGnb5rzCkbrjgLLptK1Pbvy6tvJ
R7j3IAajB8vw2BT8jCjl6U5NynL8qTz7tDbVAAwAgDyAKAwMVhLGMtu3egpxfHVd
cXqn1o2AQHP+W4qfLbv7PxcmlV/Rb0n9W5BvKDk9JR4Po4HrcXg7OOtStXo1i9H9
qL+aL3NARW9Zz3BYrEYHE28BjJq6rkX9HxGjns/6c6/bAg6CSgVHLeTzjg7+K5fc
rCSvTuWFJUU7Us/qPR9CPS86wX0rDeUt0jfw/wDFtT3pxzca8JJeIAeioa/l+KWN
wtm/SnlIptcHo14gVGyoTMCiElACEYARjACLQKhRB8zYy35LFXovSNyap+lVZ9aN
tzyPk+YXstdiXjBLM0IPK0aSS1WnvAdK0fdp7EURTyypXXJ9tBZJqnb8YEUnv78u
n8Ba8c+gCCOtHlSlN3SKuT6esAI26b9yLStdPChAUD8civLf19PjUALrmvx+4B9t
AAXbPqBaS7fiCACtOzBr7AAF+ADADHlqCyAMaRZAVGfD0UWPoroAqCEBUCICiL7T
6C/afQQAIwARSiKPj0sW99LCAMpQBCAIGfossvRYFRgoqAomRUBFZSEUQGCAEqzL
UAJBABIhIoCXtUHXcAEvVx3iWWeYASrqAWfVuKAL4+BVXv7dQAQz7VFP2kAYb7xs
gCJopAHdvV+W1gIr5blxeevxMD1bblhLi+W6/PGJBodIIgorJREmFQTkaYAZSIkw
IrIBAglRGmAE1QQA0WN5ZZxtJ1lZvRzhft/VuRfW16S6mejRAV4W1zPEcuuKxzLZ
cGv4eLinsSfC4vsyPbThC5FwnGM4vJxkk0+lMCKz4TjcipRkpRaqmnVNdTWRz+fJ
Y2nt4G9dwk06qO052XxTtvc+yAivYQwWHt3XehbUZuua69ctDyUcZzfDZX8HbxMd
0sNKjr1wn8DyjDGJuu71duXU6uen8eWczj+PbzcLoiPBftjE7uV4zv2Fl8X1AB7u
cI3IuMoqUXqmqpnhHz+Ecng8ep/J5DfwrWhJi1bxynGYmJmJjxhhurHLMLhbnlLc
PrbqttRr8qehov26rf8AT4LG2VxdrbXe4vKh4Rp44zcQ931dXrdfWw4ZZdvGoq/d
8p748J94uXbp3XxpZuOnT9UAPdnh16w4D7cr1tbnOzcSfRkwA9yeNXrDyv8AxMV0
xuL+yAHtqmnw2Ow2MW1YuwuU12XmulPNeAAbqoAAGAADoUAKUAGCAUQgIoxVyAg5
ryp/QcVieXzyrclfsPdK3PWnR7xO7HG88tzs/XhhbE4XZp1jtTrSKe9r3kAdELUo
oGoQACMAESUACOoVCABGADKAGlx+AtcwsO1cyazhNelbnulH4reboAPC2Ob3MC44
fmUHba+rHEqsrN1aJyf2Zca+Y9jetW79udu5HahNOMlxTCoraJqS3NNdKafwObWs
LzXARVvDX7F+zH0I4hSU4x+XbhqkRUB8nl9EvYrl81syt3JXrXyys3Hls/k8CbC4
XF3Mb9Mxfkoyja8lC3Zcmkm6tylL2EVUe8ATIqgxVIAWg6gAITACNjADhvrJHZxd
ue6VpdNVKRtvWeH/AKee768X/lNwkIOTUpl7KZ9usHPqpnwzqaECros10by10on1
ZZaAAHf20HSjyz95AAe4VaLr94AXPq39qAt07u2gAD1Aaab+3SAFbE2vHLrCAHj3
AewABYOntACNgsICCWomAGPIUgCs+PoroFH0V0AAQIACIAgftPoF9p9BBQmUAEUK
IPe+kW99JBQQiiKMQEUpaMb0fQBBgIqIKJSlQRlIE0AkBACVbhABLUq8QANAVKgJ
gVxr3FASLdu9nnEtPZuACWu95g6AAX4dBdOWYARyK1kAGIxsgCNiboQB131Wn9TE
w/mhLxTXwNV6sTpfvw421L9WX4QNI7MyJyCNCYhUiiCWgKkVATIFMoDJqR1ACQVQ
IDQAQGYjFTAozmKLqRQGhAEEx1ABoYAVggAKFoAD0LUCouuuYmFVETtwesIv9Fe4
MgDnnMsI8FNcxwkFGdr+mtpUV219qqW9cfcdEfWgAuFxNvF2YXbbrCaTXufWtGc6
wKfLOZzwi/oMUnes8ITXpQXbgAV1giTAijEAB5iTADzHNuYSwFqCtw271+fkrUdF
tPe+pcDzG1+0ucOSrKxgY0i/s+XevTT4BEVnwwHMbi2r3M7sZulY2oQUI9Sqs+nI
9qAHjP2Jbu/+oxOLxPVO61F/oxoj2LyADHsYezhYK3ZtxtR4RVPHi+kyq1ACUFMo
BVBZFBLUiAIlTIqgUS1I6kASAgAwQAMiAA6loAFBKAQQAEhoCAx1ABhEFFAIoCI2
QBzz1kt7WDU6V8ncT7pJx9tD03MbXlsHfhvduTXTH6y86NQiK+ZtEuivbiRLROu4
9BkFwyXb2lbrSlPwduBAA5U4/iAy3b34gBc0+7QVdX7wAVe3bzgvPr0AAX8QO3UE
Ba9uyBeWfb8AALziACMFgAIJAELEwKjHkWQBWetF0CWi6AIKJgAIgAX2n0C+0+gg
opQAQgqKPe+kW99JABCCgIQAE9H0CAgwUJEFEwgAyUCjSIJBFASAABLUSACZAgBI
gNSoCdZUqBmUBLX2i00ABrwzF2oACl1aEcggImCwgImygB7n1alTmMY/PbuR8218
DVclueT5lhXxubP6ycfiBR9FzttGykqhGhoXkZsoFBGDUegASpkdAAz1mY6dCgMo
VQgGCnmEBLQIoCRfVKAGdGSlqY8SAMmg0yoANAtSiKFlAigE8gIBEFA6gEBR1I0E
BORplAeV5thbt2Nm/h6O/hZ+UhH519qHej1bCIrVcv5nZ5hbrH6k45XLUvTg+DXD
rMPE8qwmLn5ScXC5/WW5O3N9Ljr3lRFegxGLsYSG3fuRtx0rJ6vglq+48vZ5Jg7V
xXJeVvzj6LvXHcp0J5eYqIrX3ubXeYVs8thN7WU8TOLjbtre41zcuB71KmSAitTy
/BW8BYjZhnTOUnrOT1k+k24ASgVqADLQAEsmA6gBOJFASiABUDAio6EoAQ0MmgAY
5lURFEYxkbJBRGkE4tABSOpQDaACAIEoipCMCCQACiSpGRQS1IKoigNyIqkAJ0km
tzyAAD5dxFp4e9ctb7cpR8Hkew9Y7Pk8Wp0yuwr+lHJ/Bm0ZV4LNdvxA9t/s+BRB
a6ZU85G+3GrAC9xXWmuvH8QQA61qBXUAL+IHq/GACfbUDr3gBXmJhARlAARNgBAx
MCox5ailqBRn7kIAGCAQIgAq1fQJek+ggopQApQAu99Jd76QAYgqKIQEUQgIMIpB
RKUCKmRUUQGIACEVASCKAkBAAy1ACVEYAS1rloXLMoA+G/gIAI5OuomQBAUgARAB
kWbnkr1q58lyEvCSZiMCj7MaMHA3licJYurPbtxffSj89TI0CaM5xKgNLKJnziaE
GmMmSKAxisAMhGOmRQTMZlQTxkQKqCAza5EEWAGaiJMAMypGgAyEyMigkfUIABZS
gIKEjyACEMAIgwoKMgA6kdaABJUjIoJaioRQHUFEUBalIAkI6gBImRVADJTIqgBk
7IKkBFHQZRFMYAMVQgDBAipUDUCKkKBAigADzCKgMfZJWUBj0ZOBUY1SdpABDUBo
AA1CQBQhBEU6FCAQLKgOe+sljymDVxa2p5/kyyfnobrmV2yrFy3enGEZxcXWVHnv
W/LVGoZRp851XTVdY3wrpvr21NjAHTrBff0AAurrI2ABVI68QgFr3lKgAaKwChYI
ECYLAKTBAiomJgBA9RPUgDPEyghCAKQgIpLV9BVq+ggBlABCAB730l3sAGIoBlAi
mUCKxHqOWrIAMQAToSKIohAQGCABiKgDEVAGCigJUBUAJQfiAE1SIAGwWwAhYmQF
UEAEEAHc/VrmWHt4R2L16FuULkthTls1jLPJvLJ1OFEVWX2fGUbirFqUXvi6rxR8
d2cRew7rau3Lf5EpR9lDKtsvsJo+X7fPuZ2//kzl+Woy9sWwNMvpiUEz57j6zcyj
q7Mum2v7LRRUdznA4v8AenGPW1h33TX9sqKjrujONv1lxT/0bH+f98qKjtSZw77x
4zdCx+rJ/wBsqKju1Tg33jx/Cz+o/wB4Co74cFXrHj1/Uf8AH/3EVUd+TOCfeTH8
LD/Ql+8RVR9CJnA4+tGNX+nh33T/AHyKqPoBM4WvWvErXD2X3zXxZBUd4OJL1uub
8Jb7rkl/ZAqO2M4x97Xvwi7rv/YBUdkOQfeyG/Cy/wCVfuBVR1pnKPvXa/w1z9eP
uAqOsVOSv1qtf4a5+vH3AVHWDkT9ao7sLL/kX7gFR2Ghxn72S3YVd9z/ALCKqO0U
OHP1qvvTD2l0ym/cRVR3PZ4HB36147daw67pv+2QVHddHmcEfrRj39jD/qS/fAo7
8fPb9ZeYPTyC/wDb98gCPoQ+cn6x8zely2ui1H4phVR9HpHzO+fczf8A8lr8mEF7
IkFR9O7ND5YlzfmUtcXf7p09lAKj6uUT5CljsZP0sTiJdN2f7wFR9g0ofGDnOWs5
y6ZN+1hVR9kyuWY+lctx6ZxXtZ8Y0Iqo+vJ8xwFv0sVh4/8AuQfsZ8iUIqo+o5c+
5Xb1xUH+Spy9kT5c2SKqPoy561cth6Pl7n5Nun50kfOdCKqO7y9cLC9DC3X+VOEf
ZtHCCKDtb9c+GD//ANv+w4mRQdo++Uv8Gv8Alf8A9s4rQig7V98Zf4OP/K/3DixF
B2J+uE92Ej/yv9w45Qig6+/W+7/hbf8AyS/dOPgB1773Xv8AC2v15e45IswA6797
L3+Gs98pnJ/xAB1X704iWliz4zfxOXx9gAdIl6x42VaeRh+g3+dJnP66duIFR6W7
zjH3k635JfyfUT/Vozy+e/4gBJKTk3Jycm883X26kVdUtQAJ9ffrn24gPKoAPTIi
bfQAFyyBr5wAKtfbUBvUCKH3lAikABAqggUUQEUILAAGCAEO8e8gDNEUQCIAEIAp
rV9Alq+ggBiAClAC72LewAYigCEABCAIx5asctSCilQASoSKIJKiAAgQAIoAGCAB
iAAwSoCQEoAwQgKwQAjEBRSgBSgBSgAxgEMoFRaFAqKEBRaBfHzAQDQMABoMABJA
oBoERQR0JSAI6ahhQBQMgqAoS8QKiOhI+oCgKB0AAKEnbqAIjoSdAVUR04kpBUAT
ABFSgeoUCD39PvIoImg6kFQhecCoa+Gofvyp0gVAU/CHUCgaD0faoBAUTCAqEvwh
P8QFQNBaAVC8AgKgQu3bpAqF5gvaBRHoG/YARGx7wAXZDAqBGAA0GwKKhABJ5wQA
mW4FfhADKXXx16vEDMAC6d4D6t3bvAB/iE+oIAa+5AP2FQBge4qAumgusAKR+IAI
pUBQCoBCKgEIoASgADEQBEtRrUAMoRQQhAUIQAVa9xVr3EAEIAKUAK9WJ6sAEUAG
IqAIpRBDLUciCgUVABKhIogMQAEIACKABCAAhBQGIACEEAYigBZSAIhgFIoAUoAM
QAEIAghAAWgqgFEDUCKkAqFQSkdSKKkAr4ARUpFUCKn7Mi2gIogKgQSMHaAA+3cR
7TAKm0ItrqAipO34yOvECKlXcR1AipPxke11ARUupFtaAQTeDIdpgBLuA2lwAKk1
qR7QEVJ1fjI9oCKk8O3gRVQEEq8e2upFtABIDtdXnAKeoNQIoyOoASMCpFRTrQRF
RR+wECKYyKikOhFRVr284dCKiou2YdCKio2iTZIqKjzfUOhFRQvt7x0IqKAMigAO
hFAIRADjqVABk/hyAAB8BEUA9RWRQIoAURFAOoFSKBFIAH3FCgGoiKBAkUFEACER
QAJkADHUsQAyRFACIAhFAoq1fQVa9xABCABlKIE9WLewKEMigpQIphJcQAiZkkVB
gmbREaVGJUzNlcCKqMWpkbC4EVUQVJ/JoiqI6oPya4kECqPyXWADB8k+IFQYPkpc
QKJCPydzswIqUj2LnagAERbNzgBFUCkuD8AICI8+AASEVXwAKlI6gRUgG0AEoG2i
oCUDbQAGDtooCQj20EBKBtooAwdtABIBtIAJANpcQAIHaQAEDtIADBqggGKqKAIH
IACFVAAygBSgAxAAQIAMoAUoAUoAMQAMVQgGIoAkIAGDVBAMVVxKgCBquJUAQO0u
KKgDqBtLiioCUh248SoCapDtx4lQE9SDbjxKgJSHbiVASkPlIlQEpD5SJUBOY3lI
9ZUBkGP5RdZUBkmL5RcGAGYYu2/lYAZhjVnuty8H7gAyCLZvP/Tl4MIAheSv/J7P
eUBaheQxHyrxj7wAiJfo97+XxQAQkv0a5vkvOFoEBN9Gl83tItAxzI+jfzeb8JFo
GIZf0ePFkUGFVGd5CPWRQa6psfJQ4GWgayps9iPAy0I1kTY0XBGWlGISOPD8JFQQ
lICqIAKte4q17iACKABjNCCN6sb1fbcQVCSbJdwFQOgygKUACGAFGAFKADKUAxEA
SCKAMoAEUACKABFAAxABRgAqEgABsk6AAVAyUAUlAmABbK4LwCACPZj8sfBBgBH5
OHyx8ETgBB5G38kfAyQAxvIWvkRlABifR7Xyrz+8zAoML6La+Xzs2KIorW/RLXB+
LNmRUVrfolrg/E2ZFRWr+h2v5vE2ZlUVq/oVr+bx/AbciorUfQrXGfivcbZEppFa
n6Db4z8V7jcmVRWk+gw+aXm9xvCKitF9Ah80vMb0iorR/QI/PLzG/IqK0H0CPzy8
EegIqK879Aj88vBG/IqK0H0CPzvwPQkVFef/AGevnfh+E9ERUV539nr534HoiKiv
O/s+PzvwR6EioPOfQI/O/BG/IoND9Aj88vBG/IoND9Ah88vBG+IoND9Ah80vMb0i
g0X0GHzS8xvCNA0n0G3xl5vcbkyoNP8AQrfGXivcbdhQaj6Ha/m8fwG2IoNX9Dtf
zeJtCKDVfRLXB+LNkRoGv+i2vl87NgSlBg/RbXy+d+82BKUGB9HtfIvP7zOJSoMP
yFr5ImYRQYvkbfyR8DJIooFbh8kfBExFRUezH5V4IMigNIJAAygRVKBBGyyICowQ
IFUAAKCAUDEwIqJlAgiGyKCMRAAVBABCAARMAAKBRGxkAROj18RsAIWmiZ+iiKgx
lr3FWr6DIoIoAf/Z



"""
import base64 as _b64
OFFLINE_THUMB = _b64.b64decode(OFFLINE_THUMB_B64.replace("\n", "").strip()) if OFFLINE_THUMB_B64.strip() else None

# ═══════════════════════════════════════════════════════════════════

LOGO = (
    "\n"
    "  _______                            __                \n"
    " |       .-----.----.----.---.-.----|__.--.--.--------.\n"
    " |.|   | |  -__|   _|   _|  _  |   _|  |  |  |        |\n"
    " `-|.  |-|_____|__| |__| |___._|__| |__|_____|__|__|__|\n"
    "   |:  |                                               \n"
    "   |::.|           a fishtank.live tool                \n"
    "   `---'                                               \n"
)

HEADERS = {
    "accept":       "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin":       "https://www.fishtank.live",
    "referer":      "https://www.fishtank.live/",
    "user-agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}

session           = requests.Session()
session.headers.update(HEADERS)
access_token      = None
refresh_token_val = None
live_stream_token = None
user_email        = None
user_password     = None
user_display_name = None
stop_event        = threading.Event()
processes         = {}


def ts():
    return datetime.now().strftime("%H:%M:%S")


def divider(char="═", width=52):
    print(char * width)


def print_header():
    print(LOGO)
    divider()
    print("  Terrarium — Fishtank LIVE Tool")
    divider()
    print()


# ── Credentials ───────────────────────────────────────────────────

def save_credentials(email, password):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({"email": email, "password": password}, f)
    except Exception:
        pass


def load_credentials():
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
            return data.get("email"), data.get("password")
    except Exception:
        return None, None


def clear_credentials():
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass


# ── Auth ──────────────────────────────────────────────────────────

def login(email, password):
    global access_token, refresh_token_val, live_stream_token, user_display_name
    resp = session.post(
        "https://api.fishtank.live/v1/auth/log-in",
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    s = data["session"]
    access_token      = s["access_token"]
    refresh_token_val = s["refresh_token"]
    live_stream_token = s["live_stream_token"]
    session.headers["authorization"] = f"Bearer {access_token}"
    user_display_name = data.get("user", {}).get("displayName")
    if not user_display_name:
        try:
            uid = data.get("user", {}).get("id") or s.get("user_id")
            if uid:
                pr = session.get(f"https://api.fishtank.live/v1/profile/{uid}", timeout=10)
                if pr.ok:
                    user_display_name = pr.json().get("displayName")
        except Exception:
            pass
    if user_display_name:
        print(f"  OK  Logged in as {user_display_name} ({email})")
    else:
        print(f"  OK  Logged in as {email}")


def refresh_tokens():
    global access_token, refresh_token_val, live_stream_token
    try:
        resp = session.post(
            "https://api.fishtank.live/v1/auth/refresh",
            json={"refresh_token": refresh_token_val},
            timeout=15,
        )
        resp.raise_for_status()
        s = resp.json()["session"]
        access_token      = s["access_token"]
        refresh_token_val = s["refresh_token"]
        live_stream_token = s["live_stream_token"]
        session.headers["authorization"] = f"Bearer {access_token}"
        print(f"[{ts()}] Tokens refreshed OK")
    except Exception:
        print(f"[{ts()}] Refresh failed — re-logging in...")
        login(user_email, user_password)


# ── Stream URL ────────────────────────────────────────────────────

def get_stream_url(cam_code):
    result = [None]
    found  = threading.Event()

    def try_server(letter):
        if found.is_set():
            return
        url = (
            f"https://streams-{letter}.fishtank.live"
            f"/hls/live+{cam_code}-{SEASON}/index.m3u8"
            f"?jwt={live_stream_token}&video=maxbps"
        )
        try:
            r = requests.head(url, timeout=3)
            if r.status_code == 200 and not found.is_set():
                result[0] = url
                found.set()
        except requests.RequestException:
            pass

    threads = [threading.Thread(target=try_server, args=(l,), daemon=True) for l in SERVERS]
    for t in threads:
        t.start()
    found.wait(timeout=5)
    return result[0]


# ── Cache ─────────────────────────────────────────────────────────

snap_cache = {}
snap_failed = set()
url_cache  = {}
cache_lock = threading.Lock()


def warm_cache(selected_cams):
    def _warm():
        for name, cam_code in selected_cams:
            url = get_stream_url(cam_code)
            if url:
                with cache_lock:
                    url_cache[cam_code] = url
        for name, cam_code in selected_cams:
            _refresh_snap(name, cam_code)
    threading.Thread(target=_warm, daemon=True).start()


def _refresh_snap(name, cam_code):
    with cache_lock:
        url = url_cache.get(cam_code)
    if not url:
        url = get_stream_url(cam_code)
        if not url:
            with cache_lock:
                snap_failed.add(name)
            return
        with cache_lock:
            url_cache[cam_code] = url
    try:
        cmd = ["ffmpeg", "-y", "-i", url, "-vframes", "1",
               "-f", "image2", "-vcodec", "mjpeg", "pipe:1"]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            with cache_lock:
                snap_cache[name] = result.stdout
                snap_failed.discard(name)
        else:
            with cache_lock:
                snap_failed.add(name)
    except Exception:
        with cache_lock:
            snap_failed.add(name)


def snap_refresh_loop(selected_cams):
    while not stop_event.is_set():
        for name, cam_code in selected_cams:
            if stop_event.is_set():
                break
            _refresh_snap(name, cam_code)
        stop_event.wait(10)


def get_cached_stream_url(cam_code):
    with cache_lock:
        url = url_cache.get(cam_code)
    if url:
        return url
    url = get_stream_url(cam_code)
    if url:
        with cache_lock:
            url_cache[cam_code] = url
    return url


# ── Chat ──────────────────────────────────────────────────────────

chat_messages     = []
chat_lock         = threading.Lock()
chat_seen_ids     = set()
chat_counter      = 0
MAX_MESSAGES      = 500
chat_sockets      = {}
chat_sockets_lock = threading.Lock()


def _pack_sio(type_id, data):
    return msgpack.packb(
        {"type": type_id, "data": data, "nsp": "/"},
        use_bin_type=True,
    )


def _handle_binary(data, ws, room_name=None):
    """Decode msgpack binary frame(s) and process them."""
    for skip in range(min(4, len(data))):
        try:
            unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
            unpacker.feed(data[skip:])
            decoded_any = False
            for m in unpacker:
                if isinstance(m, dict) and "type" in m:
                    decoded_any = True
                    _process_sio_packet(m, ws, room_name)
                elif isinstance(m, list) and len(m) > 0 and isinstance(m[0], dict) and "type" in m[0]:
                    decoded_any = True
                    _process_sio_packet(m[0], ws, room_name)
            if decoded_any:
                return
        except Exception:
            continue
    preview = data[:60].hex() if data else "(empty)"
    print(f"  [WS] undecoded frame ({len(data)}b): {preview}")


def _process_sio_packet(m, ws, room_name):
    """Handle a single decoded Socket.IO packet."""
    global chat_counter
    typ     = m.get("type")
    payload = m.get("data")

    if typ == 0 and isinstance(payload, dict):
        sid = payload.get("sid")
        pid = payload.get("pid")
        if sid and pid:
            tag = f" [{room_name}]" if room_name else ""
            print(f"  [WS]{tag} authenticated (sid={sid[:8]}…)")
            if room_name and room_name != "Global":
                ws.send(_pack_sio(2, ["chat:room", room_name]), CurlWsFlag.BINARY)
                print(f"  [WS]{tag} subscribed to room")

    elif typ == 2 and isinstance(payload, list) and len(payload) >= 2:
        event      = payload[0]
        event_data = payload[1]
        msgs = event_data if isinstance(event_data, list) else [event_data]

        if event == "chat:message":
            for p in msgs:
                if not isinstance(p, dict):
                    continue
                user = p.get("user", {})
                cm = {
                    "id":       str(p.get("id", "")),
                    "text":     str(p.get("message", "")),
                    "username": str(user.get("displayName", "unknown")),
                    "color":    str(user.get("customUsernameColor") or "#ffffff"),
                    "isAdmin":  bool(p.get("admin", False)),
                    "isMod":    bool((p.get("metadata") or {}).get("isMod", False)),
                    "room":     room_name or "Global",
                    "type":     "chat",
                }
                if cm["text"]:
                    with chat_lock:
                        if cm["id"] not in chat_seen_ids:
                            chat_seen_ids.add(cm["id"])
                            chat_counter += 1
                            cm["_seq"] = chat_counter
                            chat_messages.append(cm)
                            if len(chat_messages) > MAX_MESSAGES:
                                removed = chat_messages.pop(0)
                                chat_seen_ids.discard(removed["id"])

        elif event in ("tts:insert", "tts:update"):
            for p in msgs:
                if not isinstance(p, dict):
                    continue
                tts_id = str(p.get("id", ""))
                cm = {
                    "id":       f"tts-{tts_id}",
                    "text":     str(p.get("message", "")),
                    "username": str(p.get("displayName", "unknown")),
                    "color":    "#ffaa00",
                    "isAdmin":  False,
                    "isMod":    False,
                    "room":     room_name or "Global",
                    "type":     "tts",
                    "voice":    str(p.get("voice", "")),
                    "ttsRoom":  str(p.get("room", "")),
                }
                if cm["text"]:
                    with chat_lock:
                        if cm["id"] not in chat_seen_ids:
                            chat_seen_ids.add(cm["id"])
                            chat_counter += 1
                            cm["_seq"] = chat_counter
                            chat_messages.append(cm)
                            if len(chat_messages) > MAX_MESSAGES:
                                removed = chat_messages.pop(0)
                                chat_seen_ids.discard(removed["id"])


def chat_connect(bearer, room_name=None):
    """Connect to Fishtank chat via curl-cffi with recv() in a queue thread."""
    ws_url = "wss://ws.fishtank.live/socket.io/?EIO=4&transport=websocket"
    tag = f" [{room_name}]" if room_name else ""

    sess = cf_requests.Session(impersonate="chrome120")
    ws = sess.ws_connect(
        ws_url,
        headers={
            "Origin": "https://classic.fishtank.live",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        timeout=30,
    )
    print(f"  [WS]{tag} connected")

    with chat_sockets_lock:
        chat_sockets[room_name or "Global"] = ws

    recv_q = queue.Queue()

    def _recv_loop():
        try:
            while True:
                d, f = ws.recv()
                recv_q.put((d, f))
        except Exception as exc:
            recv_q.put(exc)

    threading.Thread(target=_recv_loop, daemon=True).start()

    last_recv = time.time()

    while not stop_event.is_set():
        try:
            item = recv_q.get(timeout=2)
        except queue.Empty:
            if time.time() - last_recv > 10:
                print(f"  [WS]{tag} heartbeat timeout, reconnecting")
                try:
                    ws.close()
                except Exception:
                    pass
                return
            continue

        if isinstance(item, Exception):
            print(f"  [WS]{tag} recv error: {item}")
            break

        data, flags = item
        last_recv = time.time()

        is_text   = (flags & CurlWsFlag.TEXT) != 0
        is_binary = (flags & CurlWsFlag.BINARY) != 0

        if is_text:
            text = data.decode("utf-8") if isinstance(data, bytes) else data
            if text.startswith("0"):
                print(f"  [WS]{tag} handshake, authenticating...")
                ws.send(_pack_sio(0, {"token": bearer}), CurlWsFlag.BINARY)
            elif text == "2":
                ws.send(b"3", CurlWsFlag.TEXT)
            continue

        if is_binary and data:
            _handle_binary(data, ws, room_name)


def start_chat(bearer):
    if not HAS_WS:
        print("  ! Chat disabled — run: pip install curl-cffi msgpack")
        return

    for room in CHAT_ROOMS:
        def _loop(r=room):
            while not stop_event.is_set():
                try:
                    chat_connect(bearer, room_name=r)
                except Exception as e:
                    print(f"  [WS] [{r}] error: {e}")
                with chat_sockets_lock:
                    chat_sockets.pop(r, None)
                if not stop_event.is_set():
                    print(f"  [WS] [{r}] disconnected, retrying in 5s...")
                    stop_event.wait(5)

        threading.Thread(target=_loop, daemon=True).start()

    print(f"  ✓ Chat connecting ({', '.join(CHAT_ROOMS)})...")


def send_chat_message(text, room="Global"):
    """Send a chat message through the appropriate websocket."""
    with chat_sockets_lock:
        ws = chat_sockets.get(room)
    if not ws:
        print(f"  [WS] no socket for room: {room}")
        return False
    try:
        ws.send(_pack_sio(2, ["chat:message", {"message": text}]), CurlWsFlag.BINARY)
        return True
    except Exception as e:
        print(f"  [WS] send error: {e}")
        return False


# ── Recording ─────────────────────────────────────────────────────

def start_recording(name, cam_code, save_dir, chunk_hours):
    os.makedirs(save_dir, exist_ok=True)
    url = get_stream_url(cam_code)
    if not url:
        print(f"  ✗ {name} — offline/unreachable")
        return None
    pattern  = os.path.join(save_dir, f"{name}_%Y-%m-%d_%H-%M-%S.ts")
    log_path = os.path.join(save_dir, f"{name}.log")
    cmd = [
        "ffmpeg", "-y",
        "-reconnect",          "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max","30",
        "-rw_timeout",         "15000000",
        "-i",                  url,
        "-c",                  "copy",
        "-f",                  "segment",
        "-segment_time",       str(chunk_hours * 3600),
        "-reset_timestamps",   "1",
        "-strftime",           "1",
        pattern,
    ]
    log_file = open(log_path, "w")
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
    print(f"  ✓ {name} -> {save_dir}  (log: {name}.log)")
    return proc


def stop_recording(name):
    proc = processes.pop(name, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def restart_recordings(selected_cams, save_dir, chunk_hours):
    print(f"[{ts()}] Restarting recordings...")
    for name, cam_code in selected_cams:
        stop_recording(name)
        proc = start_recording(name, cam_code, save_dir, chunk_hours)
        if proc:
            processes[name] = proc


def watchdog(selected_cams, save_dir, chunk_hours):
    while not stop_event.is_set():
        stop_event.wait(30)
        for name, cam_code in selected_cams:
            proc = processes.get(name)
            if proc and proc.poll() is not None:
                print(f"[{ts()}] [{name}] crashed — restarting")
                proc = start_recording(name, cam_code, save_dir, chunk_hours)
                if proc:
                    processes[name] = proc


def token_refresh_loop(selected_cams, save_dir, chunk_hours, do_record):
    while not stop_event.is_set():
        stop_event.wait(25 * 60)
        if stop_event.is_set():
            break
        try:
            refresh_tokens()
            with cache_lock:
                url_cache.clear()
            if do_record:
                restart_recordings(selected_cams, save_dir, chunk_hours)
        except Exception as e:
            print(f"[{ts()}] Token refresh error: {e}")


# ── Network ───────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Web viewer ────────────────────────────────────────────────────

def build_site(selected_cams, port):
    ip = get_local_ip()
    cam_list = [
        {
            "name":   name,
            "stream": f"http://{ip}:{port}/cam/{urllib.parse.quote(name)}",
            "snap":   f"http://{ip}:{port}/snap/{urllib.parse.quote(name)}",
        }
        for name, _ in selected_cams
    ]
    cam_json = json.dumps(cam_list)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Terrarium — Fishtank LIVE</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.4.12/dist/hls.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0a0a0c;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  background: #111114;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}
header h1 { font-size: 16px; font-weight: 700; }
header .sub { font-size: 11px; color: #555; }
header .count { font-size: 12px; color: #555; margin-left: auto; }
#main { display: flex; flex: 1; overflow: hidden; }
#content { flex: 1; overflow-y: auto; }
#grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
  padding: 14px;
}
.cam-card {
  background: #111114;
  border: 1px solid #1e1e22;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.cam-card:hover { border-color: #5865f2; transform: scale(1.015); }
.cam-card img {
  width: 100%;
  aspect-ratio: 16/9;
  background: #0a0a0c;
  display: block;
  object-fit: cover;
}
.cam-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
.dot.off { background: #333; }
#chat-sidebar {
  width: 290px;
  flex-shrink: 0;
  background: #0e0e10;
  border-left: 1px solid #1e1e22;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
#chat-head {
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  border-bottom: 1px solid #1e1e22;
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #555;
}
.chat-tab {
  flex: 1;
  padding: 9px 6px;
  text-align: center;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
  font-size: 10px;
  white-space: nowrap;
}
.chat-tab:hover { color: #aaa; }
.chat-tab.active { color: #e0e0e0; border-bottom-color: #5865f2; }
.chat-btn {
  background: none;
  border: none;
  color: #555;
  cursor: pointer;
  padding: 0 8px;
  font-size: 14px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
  flex-shrink: 0;
}
.chat-btn:hover { color: #e0e0e0; }
#chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  scrollbar-width: thin;
  scrollbar-color: #2a2a2e transparent;
}
.msg {
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
}
.msg:hover { background: rgba(255,255,255,0.04); }
.msg.mention { background: rgba(88,101,242,0.15); border-left: 2px solid #5865f2; }
.msg.tts-msg { background: rgba(255,170,0,0.08); border-left: 2px solid #ffaa00; font-size: 13px; padding: 5px 10px; }
.msg-name { font-weight: 700; margin-right: 4px; cursor: pointer; }
.msg-name:hover { text-decoration: underline; }
.tts-badge { font-size: 9px; color: #ffaa00; background: rgba(255,170,0,0.15); border-radius: 3px; padding: 1px 4px; margin-right: 4px; font-weight: 700; vertical-align: middle; }
.tts-voice { font-size: 10px; color: #888; margin-left: 4px; }
.msg-text { color: #bbb; font-weight: 300; }
.msg-room { font-size: 9px; color: #555; background: #1a1a1e; border-radius: 3px; padding: 1px 4px; margin-right: 4px; vertical-align: middle; }
.chat-input-wrap {
  display: flex;
  padding: 6px 8px;
  border-top: 1px solid #1e1e22;
  flex-shrink: 0;
  gap: 6px;
}
.chat-input-wrap input {
  flex: 1;
  background: #1a1a1e;
  border: 1px solid #2a2a2e;
  border-radius: 6px;
  padding: 6px 10px;
  color: #e0e0e0;
  font-size: 12px;
  outline: none;
}
.chat-input-wrap input:focus { border-color: #5865f2; }
.chat-input-wrap button {
  background: #5865f2;
  border: none;
  color: #fff;
  border-radius: 6px;
  padding: 0 12px;
  font-size: 16px;
  cursor: pointer;
  font-weight: 700;
}
.chat-input-wrap button:hover { background: #4752c4; }
#overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: #000;
  z-index: 200;
}
#overlay.open { display: flex; }
#overlay-main { flex: 1; position: relative; display: flex; flex-direction: column; }
#overlay-bar {
  position: absolute;
  top: 0; left: 0; right: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(0,0,0,0.7);
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
}
#overlay-main:hover #overlay-bar { opacity: 1; }
#overlay-title { font-size: 15px; font-weight: 700; }
#overlay-chat-toggle {
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer; font-size: 12px;
}
#overlay-chat-toggle:hover { background: rgba(255,255,255,0.2); }
#overlay-close {
  margin-left: auto;
  background: rgba(255,255,255,0.1);
  border: none; color: #fff;
  padding: 5px 14px;
  border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
#overlay-close:hover { background: rgba(255,255,255,0.2); }
#overlay video { flex: 1; width: 100%; object-fit: contain; }
#cam-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  display: flex;
  gap: 6px;
  padding: 10px 14px;
  background: rgba(0,0,0,0.7);
  overflow-x: auto;
  scrollbar-width: none;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.2s;
}
#overlay-main:hover #cam-bar { opacity: 1; }
#overlay-chat {
  width: 300px;
  background: #0e0e10;
  border-left: 1px solid #1e1e22;
  display: none;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
#overlay-chat.show { display: flex; }
#overlay-chat-head {
  padding: 0;
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid #1e1e22;
  flex-shrink: 0;
}
#overlay-chat-head .chat-tab {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #555;
}
#overlay-chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  scrollbar-width: thin;
  scrollbar-color: #2a2a2e transparent;
}
.pill {
  flex-shrink: 0;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 20px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  color: #fff;
  transition: background 0.1s;
}
.pill:hover, .pill.active { background: #5865f2; border-color: #5865f2; }
</style>
</head>
<body>
<header>
  <h1>Terrarium</h1>
  <span class="sub">Fishtank LIVE</span>
  <span class="count" id="count"></span>
</header>
<div id="main">
  <div id="content">
    <div id="grid"></div>
  </div>
  <div id="chat-sidebar">
    <div id="chat-head">
      <div class="chat-tab active" data-room="All">All</div>
      <div class="chat-tab" data-room="Global">Global</div>
      <div class="chat-tab" data-room="Season Pass">Season Pass</div>
      <button class="chat-btn" id="chat-popout" title="Pop out chat">&#x29C9;</button>
    </div>
    <div id="chat-msgs"></div>
    <div class="chat-input-wrap">
      <input type="text" id="chat-input" placeholder="Send a message..." autocomplete="off">
      <button id="chat-send">&#x203A;</button>
    </div>
  </div>
</div>
<div id="overlay">
  <div id="overlay-main">
    <div id="overlay-bar">
      <span id="overlay-title"></span>
      <button id="overlay-chat-toggle">&#x1F4AC; Chat</button>
      <button id="overlay-close">&#x2715; Close</button>
    </div>
    <video id="overlay-video" autoplay playsinline controls></video>
    <div id="cam-bar"></div>
  </div>
  <div id="overlay-chat">
    <div id="overlay-chat-head">
      <div class="chat-tab active" data-room="All">All</div>
      <div class="chat-tab" data-room="Global">Global</div>
      <div class="chat-tab" data-room="Season Pass">SP</div>
    </div>
    <div id="overlay-chat-msgs"></div>
    <div class="chat-input-wrap">
      <input type="text" id="overlay-chat-input" placeholder="Send a message..." autocomplete="off">
      <button id="overlay-chat-send">&#x203A;</button>
    </div>
  </div>
</div>
<script>
const CAMS = """ + cam_json + """;
let activeHls = null;
let activeIdx = null;
let chatPopout = null;

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function loadSnap(img, snapUrl) {
  const tmp = new Image();
  tmp.onload = () => {
    img.src = tmp.src;
    img.closest('.cam-card').querySelector('.dot').classList.remove('off');
  };
  tmp.onerror = () => {
    img.closest('.cam-card').querySelector('.dot').classList.add('off');
  };
  tmp.src = snapUrl + '?t=' + Date.now();
}

function openCam(idx) {
  activeIdx = idx;
  const cam = CAMS[idx];
  document.getElementById('overlay-title').textContent = cam.name;
  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.querySelectorAll('#cam-bar .pill').forEach((p, i) => p.classList.toggle('active', i === idx));
  const video = document.getElementById('overlay-video');
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  if (Hls.isSupported()) {
    activeHls = new Hls({
      liveSyncDurationCount: 1,
      liveMaxLatencyDurationCount: 3,
      liveDurationInfinity: true,
      lowLatencyMode: true,
      highBufferWatchdogPeriod: 1,
    });
    activeHls.loadSource(cam.stream);
    activeHls.attachMedia(video);
    activeHls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => {});
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = cam.stream;
    video.play().catch(() => {});
  }
  syncOverlayChat();
}

function closeCam() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  if (activeHls) { activeHls.destroy(); activeHls = null; }
  document.getElementById('overlay-video').src = '';
  activeIdx = null;
}

const grid   = document.getElementById('grid');
const camBar = document.getElementById('cam-bar');
document.getElementById('count').textContent = CAMS.length + ' cameras';

CAMS.forEach((cam, idx) => {
  const card = document.createElement('div');
  card.className = 'cam-card';
  card.innerHTML =
    '<img alt="' + esc(cam.name) + '">' +
    '<div class="cam-label"><span>' + esc(cam.name) + '</span>' +
    '<span class="dot off"></span></div>';
  card.addEventListener('click', () => openCam(idx));
  grid.appendChild(card);
  const img = card.querySelector('img');
  loadSnap(img, cam.snap);
  setInterval(() => loadSnap(img, cam.snap), 10000);
  const pill = document.createElement('button');
  pill.className = 'pill';
  pill.textContent = cam.name;
  pill.addEventListener('click', () => openCam(idx));
  camBar.appendChild(pill);
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeCam();
  if (e.key === 'ArrowRight' && activeIdx !== null) openCam((activeIdx + 1) % CAMS.length);
  if (e.key === 'ArrowLeft'  && activeIdx !== null) openCam((activeIdx - 1 + CAMS.length) % CAMS.length);
});
document.getElementById('overlay-close').addEventListener('click', closeCam);

// Keep video at live edge — if >3s behind, snap forward
setInterval(() => {
  const video = document.getElementById('overlay-video');
  if (!video || !activeHls || video.paused) return;
  const buffered = video.buffered;
  if (buffered.length > 0) {
    const liveEdge = buffered.end(buffered.length - 1);
    if (liveEdge - video.currentTime > 3) {
      video.currentTime = liveEdge - 0.5;
    }
  }
}, 2000);

// When user unpauses, jump to live
document.getElementById('overlay-video').addEventListener('play', () => {
  const video = document.getElementById('overlay-video');
  if (!activeHls) return;
  const buffered = video.buffered;
  if (buffered.length > 0) {
    video.currentTime = buffered.end(buffered.length - 1) - 0.5;
  }
});

// ── Chat state ──────────────────────────────────────────────────
const allMessages = [];
const seenIds = new Set();
let sidebarRoom = 'All';
let overlayRoom = 'All';
let myUsername = '';

const chatEl = document.getElementById('chat-msgs');
const overlayChatEl = document.getElementById('overlay-chat-msgs');

// Fetch our username
fetch('/me').then(r => r.json()).then(d => { myUsername = (d.displayName || '').toLowerCase(); }).catch(() => {});

// Mention sound
function playMentionSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.value = 880;
    gain.gain.value = 0.15;
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.stop(ctx.currentTime + 0.3);
  } catch {}
}

function isMentioned(text) {
  if (!myUsername) return false;
  return text.toLowerCase().includes('@' + myUsername);
}

function mentionUser(username) {
  const inputs = [
    document.getElementById('overlay-chat-input'),
    document.getElementById('chat-input'),
  ];
  for (const inp of inputs) {
    if (inp && inp.offsetParent !== null) {
      const cur = inp.value;
      inp.value = (cur ? cur.trimEnd() + ' ' : '') + '@' + username + ' ';
      inp.focus();
      return;
    }
  }
  const inp = document.getElementById('chat-input');
  if (inp) {
    inp.value = (inp.value ? inp.value.trimEnd() + ' ' : '') + '@' + username + ' ';
    inp.focus();
  }
}

// Sidebar tabs
document.querySelectorAll('#chat-head .chat-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#chat-head .chat-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    sidebarRoom = tab.dataset.room;
    renderTo(chatEl, sidebarRoom);
  });
});

// Overlay tabs
document.querySelectorAll('#overlay-chat-head .chat-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('#overlay-chat-head .chat-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    overlayRoom = tab.dataset.room;
    renderTo(overlayChatEl, overlayRoom);
  });
});

// Overlay chat toggle
document.getElementById('overlay-chat-toggle').addEventListener('click', () => {
  const panel = document.getElementById('overlay-chat');
  panel.classList.toggle('show');
  if (panel.classList.contains('show')) syncOverlayChat();
});

function syncOverlayChat() {
  renderTo(overlayChatEl, overlayRoom);
}

function renderTo(el, room) {
  el.innerHTML = '';
  const filtered = room === 'All' ? allMessages : allMessages.filter(m => m.room === room);
  filtered.forEach(m => el.appendChild(makeMsgDiv(m, room)));
  el.scrollTop = el.scrollHeight;
}

function makeMsgDiv(m, roomFilter) {
  const div = document.createElement('div');
  const mentioned = isMentioned(m.text);
  const isTts = m.type === 'tts';
  div.className = 'msg' + (mentioned ? ' mention' : '') + (isTts ? ' tts-msg' : '');

  const roomBadge = (roomFilter === 'All' && m.room && m.room !== 'Global')
    ? '<span class="msg-room">' + esc(m.room) + '</span>' : '';
  const ttsBadge = isTts ? '<span class="tts-badge">TTS</span>' : '';
  const voiceTag = isTts && m.voice ? '<span class="tts-voice">(' + esc(m.voice) + ')</span>' : '';

  div.innerHTML =
    roomBadge + ttsBadge +
    '<span class="msg-name" style="color:' + esc(m.color) + '" data-username="' + esc(m.username) + '">' + esc(m.username) + '</span>' +
    voiceTag +
    '<span class="msg-text">' + esc(m.text) + '</span>';

  const nameEl = div.querySelector('.msg-name');
  if (nameEl) {
    nameEl.addEventListener('click', (e) => {
      e.stopPropagation();
      mentionUser(nameEl.dataset.username);
    });
  }

  return div;
}

function appendToEl(el, m, roomFilter) {
  if (roomFilter !== 'All' && m.room !== roomFilter) return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  el.appendChild(makeMsgDiv(m, roomFilter));
  while (el.children.length > 200) el.removeChild(el.firstChild);
  if (atBottom) el.scrollTop = el.scrollHeight;
}

function appendMsg(m) {
  if (seenIds.has(m.id)) return;
  seenIds.add(m.id);
  allMessages.push(m);
  while (allMessages.length > 200) {
    const removed = allMessages.shift();
    seenIds.delete(removed.id);
  }
  if (isMentioned(m.text)) playMentionSound();
  appendToEl(chatEl, m, sidebarRoom);
  if (document.getElementById('overlay-chat').classList.contains('show')) {
    appendToEl(overlayChatEl, m, overlayRoom);
  }
  if (chatPopout && !chatPopout.closed) {
    try { chatPopout.appendMsg(m); } catch {}
  }
}

// ── Pop-out chat ────────────────────────────────────────────────
document.getElementById('chat-popout').addEventListener('click', () => {
  if (chatPopout && !chatPopout.closed) { chatPopout.focus(); return; }
  chatPopout = window.open('', 'terrarium_chat', 'width=340,height=600');
  const doc = chatPopout.document;
  doc.write('<!DOCTYPE html><html><head><title>Chat</title><style>' +
    '* { box-sizing: border-box; margin: 0; padding: 0; }' +
    'body { background: #0e0e10; color: #e0e0e0; font-family: -apple-system, sans-serif; display: flex; flex-direction: column; height: 100vh; }' +
    '#tabs { display: flex; border-bottom: 1px solid #1e1e22; flex-shrink: 0; }' +
    '.tab { flex: 1; padding: 8px; text-align: center; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: #555; cursor: pointer; border-bottom: 2px solid transparent; }' +
    '.tab:hover { color: #aaa; }' +
    '.tab.active { color: #e0e0e0; border-bottom-color: #5865f2; }' +
    '#msgs { flex: 1; overflow-y: auto; padding: 6px 4px; display: flex; flex-direction: column; gap: 1px; scrollbar-width: thin; scrollbar-color: #2a2a2e transparent; }' +
    '.msg { padding: 3px 10px; border-radius: 4px; font-size: 12px; line-height: 1.5; word-break: break-word; }' +
    '.msg:hover { background: rgba(255,255,255,0.04); }' +
    '.msg.mention { background: rgba(88,101,242,0.15); border-left: 2px solid #5865f2; }' +
    '.msg.tts-msg { background: rgba(255,170,0,0.08); border-left: 2px solid #ffaa00; font-size: 13px; padding: 5px 10px; }' +
    '.msg-name { font-weight: 700; margin-right: 4px; cursor: pointer; }' +
    '.msg-name:hover { text-decoration: underline; }' +
    '.tts-badge { font-size: 9px; color: #ffaa00; background: rgba(255,170,0,0.15); border-radius: 3px; padding: 1px 4px; margin-right: 4px; font-weight: 700; }' +
    '.tts-voice { font-size: 10px; color: #888; margin-left: 4px; }' +
    '.msg-text { color: #bbb; font-weight: 300; }' +
    '.msg-room { font-size: 9px; color: #555; background: #1a1a1e; border-radius: 3px; padding: 1px 4px; margin-right: 4px; }' +
    '.input-wrap { display: flex; padding: 6px 8px; border-top: 1px solid #1e1e22; gap: 6px; }' +
    '.input-wrap input { flex: 1; background: #1a1a1e; border: 1px solid #2a2a2e; border-radius: 6px; padding: 6px 10px; color: #e0e0e0; font-size: 12px; outline: none; }' +
    '.input-wrap input:focus { border-color: #5865f2; }' +
    '.input-wrap button { background: #5865f2; border: none; color: #fff; border-radius: 6px; padding: 0 12px; font-size: 16px; cursor: pointer; font-weight: 700; }' +
    '</style></head><body>' +
    '<div id="tabs">' +
    '<div class="tab active" data-room="All">All</div>' +
    '<div class="tab" data-room="Global">Global</div>' +
    '<div class="tab" data-room="Season Pass">Season Pass</div>' +
    '</div>' +
    '<div id="msgs"></div>' +
    '<div class="input-wrap">' +
    '<input type="text" id="pop-input" placeholder="Send a message..." autocomplete="off">' +
    '<button id="pop-send">&#x203A;</button>' +
    '</div>' +
    '</body></html>');
  doc.close();

  const popMsgs = chatPopout.document.getElementById('msgs');
  let popRoom = 'All';

  function esc2(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function makePopDiv(m, roomFilter) {
    const div = doc.createElement('div');
    const mentioned = myUsername && m.text.toLowerCase().includes('@' + myUsername);
    const isTts = m.type === 'tts';
    div.className = 'msg' + (mentioned ? ' mention' : '') + (isTts ? ' tts-msg' : '');

    const roomBadge = (roomFilter === 'All' && m.room && m.room !== 'Global')
      ? '<span class="msg-room">' + esc2(m.room) + '</span>' : '';
    const ttsBadge = isTts ? '<span class="tts-badge">TTS</span>' : '';
    const voiceTag = isTts && m.voice ? '<span class="tts-voice">(' + esc2(m.voice) + ')</span>' : '';

    div.innerHTML =
      roomBadge + ttsBadge +
      '<span class="msg-name" style="color:' + esc2(m.color) + '" data-username="' + esc2(m.username) + '">' + esc2(m.username) + '</span>' +
      voiceTag +
      '<span class="msg-text">' + esc2(m.text) + '</span>';

    const nameEl = div.querySelector('.msg-name');
    if (nameEl) {
      nameEl.addEventListener('click', (e) => {
        e.stopPropagation();
        const inp = doc.getElementById('pop-input');
        if (inp) {
          inp.value = (inp.value ? inp.value.trimEnd() + ' ' : '') + '@' + nameEl.dataset.username + ' ';
          inp.focus();
        }
      });
    }
    return div;
  }

  function renderPop() {
    popMsgs.innerHTML = '';
    const filtered = popRoom === 'All' ? allMessages : allMessages.filter(m => m.room === popRoom);
    filtered.forEach(m => popMsgs.appendChild(makePopDiv(m, popRoom)));
    popMsgs.scrollTop = popMsgs.scrollHeight;
  }

  chatPopout.document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      chatPopout.document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      popRoom = tab.dataset.room;
      renderPop();
    });
  });

  chatPopout.appendMsg = function(m) {
    if (popRoom !== 'All' && m.room !== popRoom) return;
    const atBottom = popMsgs.scrollHeight - popMsgs.scrollTop - popMsgs.clientHeight < 80;
    popMsgs.appendChild(makePopDiv(m, popRoom));
    while (popMsgs.children.length > 200) popMsgs.removeChild(popMsgs.firstChild);
    if (atBottom) popMsgs.scrollTop = popMsgs.scrollHeight;
  };

  renderPop();

  // Wire popout send
  const popInput = doc.getElementById('pop-input');
  const popBtn = doc.getElementById('pop-send');
  popBtn.addEventListener('click', () => {
    sendMessage(popInput.value, popRoom === 'All' ? 'Global' : popRoom);
    popInput.value = '';
    popInput.focus();
  });
  popInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(popInput.value, popRoom === 'All' ? 'Global' : popRoom);
      popInput.value = '';
    }
  });
});

// ── Send messages ───────────────────────────────────────────────
async function sendMessage(text, room) {
  if (!text.trim()) return;
  try {
    await fetch('/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text.trim(), room: room }),
    });
  } catch (e) { console.error('Send failed:', e); }
}

function wireInput(inputEl, btnEl, roomFn) {
  btnEl.addEventListener('click', () => {
    sendMessage(inputEl.value, roomFn());
    inputEl.value = '';
    inputEl.focus();
  });
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputEl.value, roomFn());
      inputEl.value = '';
    }
  });
}

wireInput(
  document.getElementById('chat-input'),
  document.getElementById('chat-send'),
  () => sidebarRoom === 'All' ? 'Global' : sidebarRoom
);

wireInput(
  document.getElementById('overlay-chat-input'),
  document.getElementById('overlay-chat-send'),
  () => overlayRoom === 'All' ? 'Global' : overlayRoom
);

// ── Polling ─────────────────────────────────────────────────────
let chatCursor = 0;

async function pollChat() {
  try {
    const r = await fetch('/chat?since=' + chatCursor);
    if (r.ok) {
      const data = await r.json();
      data.msgs.forEach(appendMsg);
      chatCursor = data.total;
    }
  } catch {}
  setTimeout(pollChat, 200);
}
pollChat();
</script>
</body>
</html>"""


def build_playlist(selected_cams, port):
    ip    = get_local_ip()
    lines = ["#EXTM3U"]
    for name, _ in selected_cams:
        url = f"http://{ip}:{port}/cam/{urllib.parse.quote(name)}"
        lines.append(f'#EXTINF:-1 tvg-name="{name}",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def make_handler(selected_cams, port):
    cam_map = {name: code for name, code in selected_cams}

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            path = self.path.strip("/").split("?")[0]

            if path in ("", "index.html"):
                body = build_site(selected_cams, port).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "health":
                self._text(200, b"ok")
                return

            if path == "me":
                body = json.dumps({"displayName": user_display_name or ""}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "chat":
                since = 0
                if "?" in self.path:
                    qs = urllib.parse.parse_qs(self.path.split("?", 1)[1])
                    try:
                        since = int(qs.get("since", [0])[0])
                    except Exception:
                        pass
                with chat_lock:
                    if since == 0:
                        msgs = list(chat_messages)
                    else:
                        msgs = [m for m in chat_messages if m.get("_seq", 0) > since]
                    seq = chat_counter
                body = json.dumps({"msgs": msgs, "total": seq}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return

            if path in ("playlist.m3u", "playlist"):
                body = build_playlist(selected_cams, port).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            if path.startswith("snap/"):
                name = urllib.parse.unquote(path[5:])
                with cache_lock:
                    body = snap_cache.get(name)
                if body:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    with cache_lock:
                        failed = name in snap_failed
                    if failed and OFFLINE_THUMB:
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(OFFLINE_THUMB)))
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(OFFLINE_THUMB)
                    else:
                        self._text(503, b"Snapshot not ready")
                return

            if path.startswith("cam/"):
                name = urllib.parse.unquote(path[4:])
                code = cam_map.get(name)
                if not code:
                    self._text(404, f"Unknown camera: {name}".encode())
                    return
                stream_url = get_cached_stream_url(code)
                if not stream_url:
                    self._text(503, b"Camera offline")
                    return
                try:
                    r = requests.get(stream_url, timeout=8)
                    if r.status_code != 200:
                        self._text(503, b"Stream unavailable")
                        return
                    ip       = get_local_ip()
                    prx_base = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                    lines    = []
                    for line in r.text.splitlines():
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#"):
                            lines.append(line)
                        else:
                            lines.append(prx_base + urllib.parse.quote(stripped, safe=""))
                    body = "\n".join(lines).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    self._text(503, f"Proxy error: {e}".encode())
                return

            if path.startswith("seg/"):
                rest  = path[4:]
                slash = rest.index("/")
                name  = urllib.parse.unquote(rest[:slash])
                seg   = urllib.parse.unquote(rest[slash + 1:])
                code  = cam_map.get(name)
                if not code:
                    self._text(404, b"Unknown camera")
                    return
                stream_url = get_cached_stream_url(code)
                if not stream_url:
                    self._text(503, b"Camera offline")
                    return
                master_base = stream_url.rsplit("/", 1)[0] + "/"
                seg_url     = master_base + seg
                try:
                    r = requests.get(seg_url, timeout=15, stream=True)
                    ct = r.headers.get("Content-Type", "")
                    if "mpegurl" in ct or seg.split("?")[0].endswith(".m3u8"):
                        this_base = seg_url.split("?")[0].rsplit("/", 1)[0] + "/"
                        ip        = get_local_ip()
                        prx_base  = f"http://{ip}:{port}/seg/{urllib.parse.quote(name)}/"
                        lines     = []
                        for line in r.text.splitlines():
                            stripped = line.strip()
                            if not stripped or stripped.startswith("#"):
                                lines.append(line)
                            else:
                                full = this_base + stripped if not stripped.startswith("http") else stripped
                                rel  = full[len(master_base):] if full.startswith(master_base) else full
                                lines.append(prx_base + urllib.parse.quote(rel, safe=""))
                        body = "\n".join(lines).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "video/mp2t")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        try:
                            for chunk in r.iter_content(65536):
                                self.wfile.write(chunk)
                        except (ConnectionAbortedError, BrokenPipeError):
                            pass
                except (ConnectionAbortedError, BrokenPipeError):
                    pass
                except Exception as e:
                    try:
                        self._text(503, f"Segment error: {e}".encode())
                    except Exception:
                        pass
                return

            self._text(404, b"Not found")

        def do_POST(self):
            path = self.path.strip("/").split("?")[0]

            if path == "chat/send":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body)
                    text = data.get("message", "").strip()
                    room = data.get("room", "Global")
                    if not text:
                        self._text(400, b"Empty message")
                        return
                    ok = send_chat_message(text, room)
                    if ok:
                        self._text(200, b"sent")
                    else:
                        self._text(503, b"No socket for room")
                except Exception as e:
                    self._text(500, f"Error: {e}".encode())
                return

            self._text(404, b"Not found")

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _text(self, code, body):
            try:
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionAbortedError, BrokenPipeError):
                pass

    return Handler


def start_proxy(selected_cams, port):
    handler = make_handler(selected_cams, port)
    srv = HTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    warm_cache(selected_cams)
    threading.Thread(target=lambda: snap_refresh_loop(selected_cams), daemon=True).start()
    start_chat(access_token)
    ip = get_local_ip()
    print(f"  ✓ Web viewer   -> http://{ip}:{port}")
    print(f"  ✓ Playlist URL -> http://{ip}:{port}/playlist.m3u")
    print(f"  (Thumbnails warming up in background...)\n")


# ── UI helpers ────────────────────────────────────────────────────

def pick_cameras():
    print("  Available cameras:\n")
    for num, (name, code) in CAMERAS.items():
        print(f"    [{num:>2}] {name}")
    print()
    print("  Enter camera numbers separated by commas,")
    print("  or press Enter for ALL cameras:")
    print()
    raw = input("  Cameras: ").strip()
    print()
    if not raw:
        return list(CAMERAS.values())
    selected = []
    for part in raw.split(","):
        key = part.strip()
        if key in CAMERAS:
            selected.append(CAMERAS[key])
        else:
            print(f"  ! Unknown number: {key} — skipping")
    return selected


def pick_save_dir():
    default = os.path.join(os.path.expanduser("~"), "terrarium_recordings")
    print(f"  Save directory (Enter for {default}):")
    raw = input("  Path: ").strip()
    return raw if raw else default


def pick_chunk_hours():
    print("\n  Chunk size in hours (Enter for 6):")
    raw = input("  Hours: ").strip()
    try:
        return int(raw) if raw else 6
    except Exception:
        return 6


def pick_proxy_port():
    print("\n  Proxy port (Enter for 8888):")
    raw = input("  Port: ").strip()
    try:
        return int(raw) if raw else 8888
    except Exception:
        return 8888


def cleanup(sig=None, frame=None):
    print(f"\n[{ts()}] Shutting down...")
    stop_event.set()
    for name in list(processes):
        stop_recording(name)
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT,  cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print_header()

    print("  Login\n")
    saved_email, saved_password = load_credentials()

    if saved_email and saved_password:
        print(f"  Saved account: {saved_email}")
        use_saved = input("  Use saved account? (Y/n): ").strip().lower()
        if use_saved in ("", "y", "yes"):
            user_email    = saved_email
            user_password = saved_password
        else:
            clear_credentials()
            user_email    = input("  Email:    ").strip()
            user_password = getpass.getpass("  Password: ")
    else:
        user_email    = input("  Email:    ").strip()
        user_password = getpass.getpass("  Password: ")

    print()
    try:
        login(user_email, user_password)
        save_credentials(user_email, user_password)
    except Exception as e:
        print(f"\n  ! Login failed: {e}")
        clear_credentials()
        sys.exit(1)

    print()
    divider("─")
    print("  Mode\n")
    print("  [1]  Watch in VLC / TV / Browser   (proxy only)")
    print("  [2]  Record to disk                (no proxy)")
    print("  [3]  Watch + Record                (proxy + record)")
    print()
    while True:
        mode = input("  Choose (1/2/3): ").strip()
        if mode in ("1", "2", "3"):
            break
        print("  Please enter 1, 2, or 3.")

    do_proxy  = mode in ("1", "3")
    do_record = mode in ("2", "3")

    print()
    divider("─")
    print("  Camera Selection\n")
    selected_cams = pick_cameras()

    if not selected_cams:
        print("  No cameras selected — exiting.")
        sys.exit(0)

    print(f"  Selected: {', '.join(n for n, _ in selected_cams)}\n")

    save_dir    = None
    chunk_hours = 6
    proxy_port  = 8888

    if do_record:
        divider("─")
        print("  Recording Options\n")
        save_dir    = pick_save_dir()
        chunk_hours = pick_chunk_hours()

    if do_proxy:
        divider("─")
        print("  Proxy Options\n")
        proxy_port = pick_proxy_port()

    print()
    divider()

    if do_proxy:
        start_proxy(selected_cams, proxy_port)

    if do_record:
        print(f"[{ts()}] Starting recordings -> {save_dir}\n")
        for name, cam_code in selected_cams:
            proc = start_recording(name, cam_code, save_dir, chunk_hours)
            if proc:
                processes[name] = proc

    threading.Thread(
        target=lambda: token_refresh_loop(selected_cams, save_dir, chunk_hours, do_record),
        daemon=True,
    ).start()

    if do_record:
        threading.Thread(
            target=lambda: watchdog(selected_cams, save_dir, chunk_hours),
            daemon=True,
        ).start()

    print(f"\n[{ts()}] Running. Ctrl+C to stop.\n")
    while not stop_event.is_set():
        time.sleep(1)
