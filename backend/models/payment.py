"""
Payment transaction model for AML risk analysis.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


class PaymentTransaction(BaseModel):
    """Payment transaction submitted for AML analysis."""
    
    payment_id: UUID = Field(default_factory=uuid4, description="Unique payment identifier")
    
    # Payer information
    originator_name: str = Field(..., min_length=1, max_length=200)
    originator_account: str = Field(..., min_length=1, max_length=50)
    originator_country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    
    # Beneficiary information
    beneficiary_name: str = Field(..., min_length=1, max_length=200)
    beneficiary_account: str = Field(..., min_length=1, max_length=50)
    beneficiary_country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    
    # Transaction details
    amount: float = Field(..., gt=0, description="Transaction amount in base currency")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")
    transaction_date: datetime
    value_date: datetime
    channel: Optional[str] = Field(None, description="Transaction channel")
    product_type: Optional[str] = Field(None, description="Product type")
    purpose_code: Optional[str] = Field(None, description="Purpose code")
    narrative: Optional[str] = Field(None, description="Narrative or description")
    
    # SWIFT fields
    swift_message_type: str = Field(..., pattern=r"MT\d{3}")
    ordering_institution: Optional[str] = Field(None, max_length=200)
    beneficiary_institution: Optional[str] = Field(None, max_length=200)
    
    # Screening flags (from upstream systems)
    sanctions_screening_result: Optional[str] = Field(None, description="PASS/FAIL/REVIEW")
    pep_screening_result: Optional[str] = Field(None, description="PASS/FAIL/REVIEW")
    edd_required: Optional[bool] = Field(None, description="Enhanced due diligence required")
    edd_performed: Optional[bool] = Field(None, description="Enhanced due diligence performed")
    str_filed_datetime: Optional[datetime] = Field(None, description="STR filed timestamp")
    client_risk_profile: Optional[str] = Field(None, description="Client risk profile")
    customer_risk_rating: Optional[str] = Field(None, description="Customer risk rating")
    
    # Metadata
    submission_timestamp: datetime = Field(default_factory=datetime.utcnow)
    submitted_by: Optional[str] = Field(None, description="User ID of submitter")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "originator_name": "Jennifer Parker",
                "originator_account": "GB39OOLA52427580832378",
                "originator_country": "GB",
                "beneficiary_name": "George Brown",
                "beneficiary_account": "GB88KUDJ48147748190437",
                "beneficiary_country": "SG",
                "amount": 15000.00,
                "currency": "USD",
                "transaction_date": "2025-11-01T10:30:00Z",
                "value_date": "2025-11-01T10:30:00Z",
                "swift_message_type": "MT103",
                "sanctions_screening_result": "PASS"
            }
        }
    }
