#!/usr/bin/env python3
"""Day 2 fake data: a 7 day schedule and six sample HMO card images (marked SAMPLE) from data/clinic.json.
Everything here is invented. Run: python3 scripts/make_data.py"""
import json, os, random, datetime
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = json.load(open(os.path.join(ROOT, 'data', 'clinic.json')))

# 1. schedule
rng = random.Random(C['schedule']['seed'])
start = datetime.date.today()  # was a fixed 2026-10-27; open_slots now skips past days, so the week starts today
days = []
for i in range(7):
    d = start + datetime.timedelta(days=i)
    key = d.strftime('%a').lower()
    hours = C['clinic']['hours'][key]
    slots = []
    if hours != 'closed':
        h0, h1 = hours.split('-')
        t = datetime.datetime.combine(d, datetime.time(int(h0[:2]), int(h0[3:])))
        end = datetime.datetime.combine(d, datetime.time(int(h1[:2]), int(h1[3:])))
        dentists = [x for x in C['clinic']['dentists'] if key in x['days']]
        while t < end:
            for dent in dentists:
                slots.append({'time': t.strftime('%H:%M'), 'dentist': dent['id'], 'taken': rng.random() < C['schedule']['taken_ratio']})
            t += datetime.timedelta(minutes=C['schedule']['slot_minutes'])
    days.append({'date': d.isoformat(), 'day': key, 'hours': hours, 'slots': slots})
json.dump({'_note': 'fake schedule, generated', 'generated': datetime.date.today().isoformat(), 'days': days},
          open(os.path.join(ROOT, 'data', 'schedule.json'), 'w'), indent=1)
open_count = sum(1 for d in days for s in d['slots'] if not s['taken'])
print('schedule: 7 days,', open_count, 'open slots')

# 2. sample HMO cards
os.makedirs(os.path.join(ROOT, 'data', 'cards'), exist_ok=True)
def font(size, bold=False):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()
colors = {}  # one neutral color for every card: no insurer's brand colors or logos on a demo card
for p in C['patients']:
    # a photo of a card on a table: grey background, the card tilted slightly, so SAM has something to crop
    W, H = 1200, 900
    im = Image.new('RGB', (W, H), (210, 205, 198))
    d = ImageDraw.Draw(im)
    for y in range(0, H, 6): d.line([(0, y), (W, y)], fill=(204, 199, 192))
    card = Image.new('RGB', (760, 480), (72, 84, 104))
    cd = ImageDraw.Draw(card)
    cd.rectangle([0, 0, 760, 110], fill=tuple(max(0, c - 30) for c in (72, 84, 104)))
    cd.text((28, 30), p['hmo'], font=font(44, True), fill=(255, 255, 255))
    cd.text((28, 140), 'MEMBER', font=font(22), fill=(230, 230, 230))
    cd.text((28, 168), p['name'].upper(), font=font(36, True), fill=(255, 255, 255))
    cd.text((28, 230), 'MEMBER ID', font=font(22), fill=(230, 230, 230))
    cd.text((28, 258), p['member_id'], font=font(34, True), fill=(255, 255, 255))
    cd.text((420, 230), 'VALID THRU', font=font(22), fill=(230, 230, 230))
    cd.text((420, 258), '12/2027', font=font(34, True), fill=(255, 255, 255))
    cd.text((28, 330), 'PLAN: DENTAL BASIC', font=font(24), fill=(240, 240, 240))
    cd.text((28, 410), f"DEMO SAMPLE. NOT ISSUED BY {p['hmo'].upper()}. HACKATHON 2026.", font=font(20, True), fill=(255, 230, 80))
    card = card.resize((950, 600))  # the card fills about half of the photo, like a card held close to the camera
    card = card.rotate(rng.uniform(-6, 6), expand=True, fillcolor=(210, 205, 198))
    im.paste(card, ((W - card.width) // 2, (H - card.height) // 2))
    d = ImageDraw.Draw(im)
    d.text((20, 20), 'SAMPLE', font=font(40, True), fill=(120, 30, 30))
    out = os.path.join(ROOT, 'data', 'cards', f"{p['id']}_{p['hmo'].lower().replace(' ', '_')}.jpg")
    im.save(out, quality=88)
    print('card', out)
