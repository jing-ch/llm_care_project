from django.db import models


class Provider(models.Model):
    """Referring provider; NPI is 10-digit unique identifier."""
    name = models.CharField(max_length=255)
    npi = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (NPI: {self.npi})"


class Patient(models.Model):
    """Patient; MRN is 6-digit unique identifier."""
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    mrn = models.CharField(max_length=6, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name}, {self.first_name} (MRN: {self.mrn})"


class Order(models.Model):
    """Single order (one medication) linking patient and provider."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='orders')
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='orders')
    medication_name = models.CharField(max_length=255)
    primary_diagnosis = models.CharField(max_length=512, blank=True)
    additional_diagnoses = models.JSONField(default=list, help_text="List of diagnosis strings")
    medication_history = models.JSONField(default=list, help_text="List of medication history entries")
    patient_records = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} {self.medication_name}"


class CarePlan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='care_plan')
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CarePlan for Order #{self.order_id} ({self.status})"
