"""
Generate sample_khatauni.png to test file upload in BhoomiVoice.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Create an image canvas resembling an official revenue document (A4 proportions)
width, height = 1000, 750
img = Image.new("RGB", (width, height), color=(253, 252, 248))
draw = ImageDraw.Draw(img)

# Outer decorative border
draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(120, 110, 90), width=3)
draw.rectangle([(26, 26), (width - 26, height - 26)], outline=(180, 170, 150), width=1)

# Header Section
draw.rectangle([(30, 30), (width - 30, 110)], fill=(240, 244, 238), outline=(140, 160, 130), width=2)
draw.text((320, 45), "राजस्व परिषद उत्तर प्रदेश - खतौनी (अधिकार अभिलेख)", fill=(20, 50, 30))
draw.text((360, 75), "गाँव: रामपुर कलां | परगना: देहात | तहसील: सदर | जनपद: वाराणसी", fill=(60, 80, 70))

# Record Metadata Table
headers = ["खाता संख्या", "फसली वर्ष", "खातेदार का नाम व पिता का नाम", "खसरा (गाटा) सं०", "क्षेत्रफल (हेक्टेयर)", "देय लगान"]
col_widths = [110, 110, 310, 140, 140, 130]

y_start = 140
draw.rectangle([(30, y_start), (width - 30, y_start + 40)], fill=(225, 235, 220), outline=(100, 130, 90), width=1)

x_pos = 35
for idx, h in enumerate(headers):
    draw.text((x_pos, y_start + 12), h, fill=(10, 40, 20))
    x_pos += col_widths[idx]

# Row 1 Data
row_y = y_start + 45
draw.rectangle([(30, row_y), (width - 30, row_y + 90)], fill=(255, 255, 255), outline=(190, 190, 180), width=1)

row_data = [
    "00128",
    "1430-1435",
    "रामेश्वर प्रसाद\nसुपुत्र हरिनारायण\n(निवासी: रामपुर कलां)",
    "342/2 ख",
    "0.4520\n(~1.11 एकड़)",
    "₹ 48.50"
]

x_pos = 35
for idx, d in enumerate(row_data):
    draw.text((x_pos, row_y + 12), d, fill=(20, 20, 20))
    x_pos += col_widths[idx]

# Legal & Remarks Section
remarks_y = row_y + 110
draw.rectangle([(30, remarks_y), (width - 30, remarks_y + 140)], fill=(248, 249, 250), outline=(180, 180, 180), width=1)
draw.text((45, remarks_y + 15), "【कैफियत एवं आदेश भाग (Column 7-12)】", fill=(40, 40, 40))
draw.text((45, remarks_y + 45), "• भूमि श्रेणी: संक्रमणीय अधिकार वाले भूमिधर (Category 1-A)", fill=(50, 50, 50))
draw.text((45, remarks_y + 75), "• बैंक अथवा वित्तीय संस्था से कोई बंधक (Mortgage) दर्ज नहीं है।", fill=(30, 90, 40))
draw.text((45, remarks_y + 105), "• किसी न्यायालय का कोई स्थगन (Stay Order) या विवाद प्रविष्टि नहीं है।", fill=(30, 90, 40))

# Disclaimer Footer
footer_y = height - 90
draw.rectangle([(30, footer_y), (width - 30, footer_y + 50)], fill=(255, 248, 230), outline=(220, 180, 80), width=1)
draw.text((45, footer_y + 15), "सूचना: यह प्रतिदर्श खतौनी केवल अभिलेखीय वाचन सहायक के रूप में प्रदर्शित है। विधिक स्वामित्व का अंतिम प्रमाण नहीं है।", fill=(120, 80, 0))

img.save("sample_khatauni.png")
print("Saved sample_khatauni.png successfully.")
