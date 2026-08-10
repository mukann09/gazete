#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36'

RADARS={
    'google_trends':'https://trends.google.com/trending/rss?geo=TR',
    'google_news':'https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr',
    'x_trends24':'https://trends24.in/turkey/',
    'x_getdaytrends':'https://getdaytrends.com/turkey/',
    'reddit_new':'https://www.reddit.com/r/Turkey/new/.rss?limit=25',
}

BASE_SCORE={
    'google_news':180,
    'google_trends':165,
    'x_trends24':155,
    'x_getdaytrends':150,
    'legacy':125,
    'reddit_new':95,
}

NOISE={
    'pazartesi','salı','sali','çarşamba','carsamba','perşembe','persembe','cuma','cumartesi','pazar',
    'günaydın','gunaydin','iyi geceler','hayırlı sabahlar','hayirli sabahlar','mutlu yıllar','mutlu yillar'
}


def req(url,timeout=10):
    r=urllib.request.Request(url,headers={
        'User-Agent':UA,
        'Accept-Language':'tr-TR,tr;q=0.9,en;q=0.5',
        'Accept':'application/rss+xml,application/xml,text/xml,text/html,*/*'
    })
    with urllib.request.urlopen(r,timeout=timeout) as resp:
        return resp.read()


def clean(text):
    text=html.unescape(text or '')
    text=re.sub(r'<[^>]+>',' ',text)
    text=re.sub(r'\s+',' ',text).strip(' \t\r\n-–—|')
    return text


def norm(text):
    t=clean(text).lower().lstrip('#')
    t=re.sub(r'[^a-z0-9çğıöşü]+',' ',t)
    return ' '.join(t.split())


def acceptable(title):
    t=clean(title)
    n=norm(t)
    if len(t)<3 or len(t)>150:
        return False
    if n in NOISE:
        return False
    if re.fullmatch(r'\d+',n or ''):
        return False
    return True


def parse_rss(url,source,limit):
    out=[]
    try:
        root=ET.fromstring(req(url))
    except Exception:
        return out

    channel=root.find('channel')
    if channel is not None:
        items=channel.findall('item')
        for i,item in enumerate(items[:limit]):
            title=clean(item.findtext('title') or '')
            if acceptable(title):
                out.append((title,source,i))
        return out

    ns={'atom':'http://www.w3.org/2005/Atom'}
    entries=root.findall('atom:entry',ns) or root.findall('{http://www.w3.org/2005/Atom}entry')
    for i,item in enumerate(entries[:limit]):
        title=clean(item.findtext('{http://www.w3.org/2005/Atom}title') or '')
        if acceptable(title):
            out.append((title,source,i))
    return out


class LinkCollector(HTMLParser):
    def __init__(self,mode):
        super().__init__()
        self.mode=mode
        self.active=False
        self.buf=[]
        self.items=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()!='a':
            return
        d=dict(attrs)
        href=d.get('href','')
        ok=False
        if self.mode=='trends24':
            ok='/turkey/' in href or '/trend/' in href
        elif self.mode=='getdaytrends':
            ok='/turkey/trend/' in href or '/trend/' in href
        if ok:
            self.active=True; self.buf=[]
    def handle_data(self,data):
        if self.active:
            self.buf.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.active:
            t=clean(''.join(self.buf))
            if acceptable(t):
                self.items.append(t)
            self.active=False; self.buf=[]


def parse_x_proxy(url,source,mode,limit=30):
    try:
        text=req(url).decode('utf-8','replace')
    except Exception:
        return []
    p=LinkCollector(mode)
    try:
        p.feed(text)
    except Exception:
        return []
    out=[]; seen=set()
    for t in p.items:
        n=norm(t)
        if not n or n in seen:
            continue
        seen.add(n)
        # Navigation labels are common in these pages.
        if n in {'view details','browse all','timeline','tag cloud','table','now','yesterday'}:
            continue
        out.append((t,source,len(out)))
        if len(out)>=limit:
            break
    return out


def fetch_multi_radar(cfg,legacy_fetch):
    candidates=[]

    # Existing source remains one signal, not the whole agenda.
    try:
        for i,item in enumerate(legacy_fetch(cfg)):
            t=item.get('radar_title','')
            if acceptable(t):
                candidates.append((t,'legacy',i))
    except Exception as e:
        print('Legacy radar atlandı:',e,flush=True)

    sources=[
        ('google_trends',lambda:parse_rss(RADARS['google_trends'],'google_trends',30)),
        ('google_news',lambda:parse_rss(RADARS['google_news'],'google_news',35)),
        ('x_trends24',lambda:parse_x_proxy(RADARS['x_trends24'],'x_trends24','trends24',30)),
        ('x_getdaytrends',lambda:parse_x_proxy(RADARS['x_getdaytrends'],'x_getdaytrends','getdaytrends',30)),
        ('reddit_new',lambda:parse_rss(RADARS['reddit_new'],'reddit_new',20)),
    ]

    for name,fn in sources:
        try:
            rows=fn()
            print(f'Radar {name}: {len(rows)} aday',flush=True)
            candidates.extend(rows)
        except Exception as e:
            print(f'Radar {name} atlandı: {e}',flush=True)

    merged={}
    for title,source,pos in candidates:
        n=norm(title)
        if not n:
            continue
        rec=merged.setdefault(n,{
            'radar_title':clean(title),
            'count':0,
            'score':0,
            'radar_sources':set(),
        })
        rec['radar_sources'].add(source)
        # Rank signal + recency/position bonus.
        rec['score']=max(rec['score'],BASE_SCORE.get(source,80)+max(0,40-pos))
        rec['count']+=1

    # If the same phrase appears in more than one independent radar, promote it hard.
    for rec in merged.values():
        rec['score'] += 90*(len(rec['radar_sources'])-1)
        rec['radar_sources']=sorted(rec['radar_sources'])

    ranked=sorted(merged.values(),key=lambda x:(x['score'],x['count']),reverse=True)
    limit=max(int(cfg.get('radar_scan_limit',40)),40)
    return ranked[:limit]
