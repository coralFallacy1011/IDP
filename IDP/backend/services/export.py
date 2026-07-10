from reportlab.pdfgen import canvas

def text_to_pdf(text, path):
    c = canvas.Canvas(path)
    y = 800

    for line in text.split("\n"):
        c.drawString(40, y, line[:110])
        y -= 20

        if y < 40:
            c.showPage()
            y = 800

    c.save()