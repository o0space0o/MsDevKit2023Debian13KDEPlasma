#!/usr/bin/env python3
"""Render the public beginner and implementation guide. Requires reportlab."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
import unicodedata

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor('#132D46')
TEAL = colors.HexColor('#007F86')
INK = colors.HexColor('#263747')
MUTED = colors.HexColor('#546879')
PALE = colors.HexColor('#EEF5F7')
WIDTH = A4[0] - 38 * mm
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle('BodyGuide', fontName='Helvetica', fontSize=10,
    leading=14.2, textColor=INK, spaceAfter=7, splitLongWords=True))
STYLES.add(ParagraphStyle('Chapter', fontName='Helvetica-Bold', fontSize=23,
    leading=28, textColor=NAVY, spaceAfter=18, keepWithNext=True))
STYLES.add(ParagraphStyle('Section', fontName='Helvetica-Bold', fontSize=14,
    leading=18, textColor=TEAL, spaceBefore=15, spaceAfter=8, keepWithNext=True))
STYLES.add(ParagraphStyle('CoverLead', parent=STYLES['Section']))
STYLES.add(ParagraphStyle('Subsection', fontName='Helvetica-Bold', fontSize=11,
    leading=15, textColor=NAVY, spaceBefore=10, spaceAfter=7, keepWithNext=True))
STYLES.add(ParagraphStyle('Cell', parent=STYLES['BodyGuide'], fontSize=8.7,
    leading=12, spaceAfter=0))
STYLES.add(ParagraphStyle('CellHead', parent=STYLES['Cell'], fontName='Helvetica-Bold',
    textColor=colors.white))
STYLES.add(ParagraphStyle('CodeGuide', parent=STYLES['BodyGuide'], fontName='Courier',
    fontSize=8.3, leading=12, backColor=PALE, borderPadding=9, spaceBefore=5, spaceAfter=12))
STYLES.add(ParagraphStyle('Step', parent=STYLES['BodyGuide'], leftIndent=17,
    firstLineIndent=-17, spaceAfter=8))
STYLES.add(ParagraphStyle('CoverTitle', fontName='Helvetica-Bold', fontSize=28,
    leading=34, textColor=NAVY, spaceAfter=18))
STYLES.add(ParagraphStyle('Kicker', fontName='Helvetica-Bold', fontSize=10,
    leading=14, textColor=TEAL, spaceAfter=16))


def normalize(text):
    for old, new in {'\u2011': '-', '\u2013': '-', '\u2014': ' - ', '\u2018': "'",
                     '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2192': ' > ',
                     '\u00a0': ' '}.items():
        text = text.replace(old, new)
    return unicodedata.normalize('NFC', text)


def inline(text, show_urls=False):
    text = escape(normalize(text))
    def link(match):
        title, url = match.groups()
        if url.startswith(('https://', 'http://')):
            suffix = '<br/><font size="8" color="#546879">' + url + '</font>' if show_urls else ''
            return '<a href="' + url + '" color="#007F86">' + title + '</a>' + suffix
        return title
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    return text


class Guide(BaseDocTemplate):
    def __init__(self, output):
        super().__init__(str(output), pagesize=A4, leftMargin=19*mm, rightMargin=19*mm,
            topMargin=23*mm, bottomMargin=21*mm, title='DevKit2023CustomLinux - Complete Guide',
            author='DevKit2023CustomLinux Project', subject='Version 1.0.0 setup and implementation',
            pageCompression=1)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='guide', frames=[frame], onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(1)
        canvas.line(19*mm, A4[1]-15*mm, A4[0]-19*mm, A4[1]-15*mm)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.setFillColor(NAVY)
        canvas.drawString(19*mm, A4[1]-12*mm, 'DevKit2023CustomLinux')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(A4[0]-19*mm, A4[1]-12*mm, 'VERSION 1.0.0')
        canvas.setFillColor(MUTED)
        canvas.drawString(19*mm, 12*mm, 'SETUP + IMPLEMENTATION  |  6 SEPTEMBER 2026')
        canvas.drawRightString(A4[0]-19*mm, 12*mm, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ('Chapter', 'Section'):
            level = 0 if flowable.style.name == 'Chapter' else 1
            label = flowable.getPlainText()
            key = 'section-' + str(self.seq.nextf('heading'))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(label, key, level=level, closed=False)
            self.notify('TOCEntry', (level, label, self.page, key))


def markdown(path, title):
    lines = normalize(path.read_text(encoding='utf-8')).splitlines()
    story = [PageBreak(), Paragraph(title, STYLES['Chapter'])]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('# '):
            i += 1
            continue
        if line.startswith('```'):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code.append(escape(lines[i]))
                i += 1
            story.append(Paragraph('<br/>'.join(code), STYLES['CodeGuide']))
            i += 1
            continue
        if line.startswith('##'):
            style = 'Subsection' if line.startswith('###') else 'Section'
            story.append(Paragraph(inline(line.lstrip('#').strip()), STYLES[style]))
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', cell) for cell in cells):
                    style = STYLES['CellHead'] if not rows else STYLES['Cell']
                    rows.append([Paragraph(inline(cell), style) for cell in cells])
                i += 1
            widths = [WIDTH * x for x in ([.31, .69] if len(rows[0]) == 2 else [.22, .40, .38])]
            table = Table(rows, colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), NAVY),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [PALE, colors.white]),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 7),
                ('BOTTOMPADDING', (0,0), (-1,-1), 7),
                ('LINEBELOW', (0,0), (-1,0), .8, TEAL),
            ]))
            story.extend([table, Spacer(1, 10)])
            continue
        paragraph = [line]
        is_step = bool(re.match(r'^(?:\d+\. |[-*] )', line))
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(?:#|\||```|\d+\. |[-*] )', lines[i].strip()):
            paragraph.append(lines[i].strip())
            i += 1
        text = ' '.join(paragraph)
        if text.startswith('- '):
            text = '&#8226; ' + inline(text[2:], show_urls=path.name == 'UPSTREAM.md')
        else:
            text = inline(text, show_urls=path.name == 'UPSTREAM.md')
        story.append(Paragraph(text, STYLES['Step' if is_step else 'BodyGuide']))
    return story


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/DevKit2023CustomLinux-Guide.pdf')
    args = parser.parse_args()
    story = [Spacer(1, 24*mm), Paragraph('THE COMPLETE GUIDE', STYLES['Kicker']),
             Paragraph('DevKit2023CustomLinux', STYLES['CoverTitle']),
             Paragraph('From fresh Windows to KDE Plasma.<br/>One launcher. One finished ISO.', STYLES['CoverLead']),
             Spacer(1, 13*mm),
             Paragraph('Microsoft Windows Dev Kit 2023<br/>Blackrock / Qualcomm SC8280XP<br/>Debian 13 ARM64 + pinned patched kernel', STYLES['BodyGuide']),
             Spacer(1, 12*mm)]
    flow = Table([[Paragraph(t, STYLES['CellHead']) for t in
                   ('1. PREPARE WINDOWS', '2. BUILD YOUR ISO', '3. WRITE USB', '4. INSTALL LINUX')]],
                 colWidths=[WIDTH/4]*4)
    flow.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),12), ('BOTTOMPADDING',(0,0),(-1,-1),12),
        ('LEFTPADDING',(0,0),(-1,-1),9), ('RIGHTPADDING',(0,0),(-1,-1),9)]))
    story.extend([flow, Spacer(1, 14*mm),
        Paragraph('<b>Important:</b> the public project works with independent target preparation. '
                  'Each finished ISO contains private firmware and identity for one selected Dev Kit. '
                  'Publish the source, never the contents of ISO.', STYLES['BodyGuide']),
        Paragraph('Owner-accepted 1.0.0 baseline. The working image is preserved unchanged. '
                  'This guide does not certify every peripheral, another kit or an arbitrary Windows disk layout.', STYLES['BodyGuide']),
        PageBreak(), Paragraph('Contents', STYLES['CoverTitle'])])
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle('Contents0', fontName='Helvetica-Bold', fontSize=11,
        leading=14, textColor=NAVY, spaceBefore=7, spaceAfter=0),
        ParagraphStyle('Contents1', fontName='Helvetica', fontSize=9, leading=10,
                       leftIndent=12, firstLineIndent=0, textColor=INK, spaceBefore=0, spaceAfter=0)]
    story.append(toc)
    for name, title in [('SETUP.md','Part 1 / Beginner setup'),
                        ('docs/IMPLEMENTATION.md','Part 2 / Implementation reference'),
                        ('docs/UPSTREAM.md','Part 3 / Sources and provenance')]:
        story.extend(markdown(ROOT/name, title))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Guide(args.output).multiBuild(story)
    print('Created ' + str(args.output))


if __name__ == '__main__':
    main()
