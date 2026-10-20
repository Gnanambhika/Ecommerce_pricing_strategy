"""E-commerce Pricing Strategy & Profitability Intelligence.

Core analytics package: data generation, validation, SQL access, financial
metrics, price-elasticity estimation and the pricing scenario engine. The
Streamlit UI lives in ``pricing_intel.ui`` and only *consumes* these modules,
so every business rule can be unit-tested without a browser.
"""

__version__ = "1.0.0"
