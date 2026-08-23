from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from pathlib import Path

out = Path(__file__).parent / "certificate.pdf"
w, h = A4
c = canvas.Canvas(str(out), pagesize=A4)

c.setStrokeColor(HexColor("#22d3ee"))
c.setLineWidth(3)
c.rect(40, 40, w - 80, h - 80)
c.setStrokeColor(HexColor("#a78bfa"))
c.setLineWidth(1)
c.rect(50, 50, w - 100, h - 100)

c.setFillColor(HexColor("#22d3ee"))
c.setFont("Helvetica-Bold", 14)
c.drawCentredString(w / 2, h - 120, "CERTIFICATE OF COMPLETION")

c.setFillColor(HexColor("#e8edf5"))
c.setFont("Helvetica", 13)
c.drawCentredString(w / 2, h - 170, "This is to certify that the project")

c.setFillColor(HexColor("#22d3ee"))
c.setFont("Helvetica-Bold", 28)
c.drawCentredString(w / 2, h - 230, "SentinelAgent")

c.setFillColor(HexColor("#e8edf5"))
c.setFont("Helvetica", 13)
c.drawCentredString(w / 2, h - 270, "Autonomous Anomaly Detection")
c.drawCentredString(w / 2, h - 292, "& Self-Healing Agent Platform")

c.setFont("Helvetica", 13)
c.drawCentredString(w / 2, h - 340, "was created by")

c.setFillColor(HexColor("#22d3ee"))
c.setFont("Helvetica-Bold", 32)
c.drawCentredString(w / 2, h - 395, "Armaansalik")

c.setFillColor(HexColor("#e8edf5"))
c.setFont("Helvetica", 12)
c.drawCentredString(w / 2, h - 440, "MSME Hackathon 2026")
c.setFont("Helvetica", 11)
c.drawCentredString(w / 2, h - 462, "SentinelAgent - Domain-agnostic anomaly detection with AI agent reasoning")

c.setFillColor(HexColor("#7a8ba8"))
c.setFont("Helvetica", 10)
c.drawCentredString(w / 2, 100, "github.com/Armaansalik/Anamoly_detection")
c.drawCentredString(w / 2, 80, "Built with FastAPI, React, scikit-learn, Three.js")

c.save()
print(f"Created: {out} ({out.stat().st_size} bytes)")
