"""Single source of truth for the Scam Shield label taxonomy.

Dataset preparation, training, inference and evaluation all import from here
so that class names (and their ORDER, which fixes the model's output-layer
indices) can never drift apart.

Taxonomy (single-label, 6 classes). A message gets exactly one label: the
scammer's PRIMARY goal. Boundary rule for labelers: if a prize scam contains
a phishing link, label it `fake_prize` (the goal is the fee, not the
credential theft). On ties, break with PRECEDENCE below.
"""

NOT_SCAM = "not_scam"

# Model output order — do not reorder once a model has been trained.
SCAM_LABELS = [
    "phishing",
    "fake_prize",
    "loan_scam",
    "impersonation",
    "investment_fraud",
]

ALL_LABELS = SCAM_LABELS + [NOT_SCAM]

LABEL_DESCRIPTIONS = {
    "phishing": "Steals credentials via fake login pages or urgent verification links (KYC, SIM, Aadhaar, netbanking).",
    "fake_prize": "Claims the victim won a prize/lottery and must pay an upfront fee to claim it.",
    "loan_scam": "Fake loan approval that demands a processing/verification fee before disbursal.",
    "impersonation": "Poses as a trusted person or authority (bank, police, family, boss, hospital).",
    "investment_fraud": "Promises guaranteed/high returns on investments, crypto, trading or work-from-home schemes.",
    "not_scam": "Legitimate message: personal chat, OTPs, official alerts, promotions.",
}

# Tie-break precedence when a message plausibly matches several intents.
PRECEDENCE = [
    "impersonation",
    "phishing",
    "investment_fraud",
    "loan_scam",
    "fake_prize",
]


def is_scam_label(label: str) -> bool:
    """True for every label except `not_scam`."""
    return label != NOT_SCAM
