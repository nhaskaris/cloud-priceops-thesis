"""
Management command to seed demo ML models for presentation/testing purposes.
Usage: python manage.py seed_demo_models
"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from model_registry.models import MLEngine, ModelCoefficient
import pickle
import json
import random
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Seeds demo ML models with varied performance metrics for presentation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of demo models to create (default: 10)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo models before seeding',
        )

    def handle(self, *args, **options):
        count = options['count']
        
        if options['clear']:
            deleted = MLEngine.objects.filter(name__startswith='Demo_').delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted[0]} existing demo models'))

        # Model type templates with realistic performance ranges
        model_templates = [
            {
                'model_type': 'Linear_Regression',
                'r2_range': (0.75, 0.88),
                'mape_range': (15, 35),
                'features': ['const', 'vcpu_count', 'memory_gb', 'region_encoded', 'os_encoded']
            },
            {
                'model_type': 'Ridge_Regression',
                'r2_range': (0.82, 0.92),
                'mape_range': (12, 25),
                'features': ['const', 'log_vcpu', 'log_memory', 'region_encoded', 'os_encoded', 'tenancy_encoded']
            },
            {
                'model_type': 'Random_Forest',
                'r2_range': (0.88, 0.95),
                'mape_range': (8, 18),
                'features': ['vcpu_count', 'memory_gb', 'region', 'os', 'tenancy', 'product_family']
            },
            {
                'model_type': 'XGBoost',
                'r2_range': (0.90, 0.97),
                'mape_range': (5, 15),
                'features': ['vcpu_count', 'memory_gb', 'region', 'os', 'tenancy', 'product_family', 'pricing_model']
            },
            {
                'model_type': 'Gradient_Boosting',
                'r2_range': (0.89, 0.96),
                'mape_range': (6, 16),
                'features': ['vcpu_count', 'memory_gb', 'region', 'os', 'tenancy']
            },
            {
                'model_type': 'Neural_Network',
                'r2_range': (0.85, 0.94),
                'mape_range': (9, 22),
                'features': ['vcpu_count', 'memory_gb', 'region_encoded', 'os_encoded', 'tenancy_encoded']
            },
            {
                'model_type': 'Hedonic_Regression',
                'r2_range': (0.78, 0.90),
                'mape_range': (13, 28),
                'features': ['const', 'log_vcpu', 'log_memory', 'region_us_east', 'os_linux', 'tenancy_shared']
            },
            {
                'model_type': 'Lasso_Regression',
                'r2_range': (0.76, 0.87),
                'mape_range': (14, 30),
                'features': ['const', 'vcpu_count', 'memory_gb', 'region_encoded', 'os_encoded']
            },
        ]

        created_count = 0
        base_date = datetime.now() - timedelta(days=180)  # Start 6 months ago

        for i in range(count):
            # Select a random template
            template = random.choice(model_templates)
            
            # Generate realistic metrics within the template range
            r_squared = random.uniform(*template['r2_range'])
            mape = random.uniform(*template['mape_range'])
            rmse = mape * random.uniform(0.8, 1.2)  # RMSE roughly correlates with MAPE
            
            # Create timestamp spread over past 6 months
            timestamp_created = base_date + timedelta(days=random.randint(0, 180))
            
            # Generate version string
            version_date = timestamp_created.strftime('%Y.%m.%d')
            version = f"{version_date}.{i+1:02d}"
            
            # Create model name
            name = f"Demo_{template['model_type']}_{i+1}"
            
            # Create dummy model binary (a simple dict pickled)
            dummy_model = {
                'type': template['model_type'],
                'coefficients': [random.uniform(-5, 5) for _ in template['features']],
                'intercept': random.uniform(0, 2),
            }
            model_binary = pickle.dumps(dummy_model)
            
            # Create dummy encoder
            dummy_encoder = {'feature_mapping': {f: idx for idx, f in enumerate(template['features'])}}
            encoder_binary = pickle.dumps(dummy_encoder)
            
            # Determine if active (only one per type should be active)
            is_active = (i % (count // len(model_templates) + 1)) == 0 if count >= len(model_templates) else False
            
            # Create the engine
            engine = MLEngine.objects.create(
                name=name,
                model_type=template['model_type'],
                version=version,
                model_binary=ContentFile(model_binary, name=f'{name}_model.pkl'),
                encoder_binary=ContentFile(encoder_binary, name=f'{name}_encoder.pkl'),
                feature_names=template['features'],
                log_transformed_features=['log_vcpu', 'log_memory'] if 'log_' in str(template['features']) else [],
                categorical_features=['region', 'os', 'tenancy'] if 'region' in str(template['features']) else [],
                r_squared=r_squared,
                mape=mape,
                rmse=rmse,
                training_sample_size=random.randint(5000, 50000),
                is_active=is_active,
                timestamp_created=timestamp_created,
                metadata={
                    'training_date': timestamp_created.isoformat(),
                    'demo': True,
                    'framework': random.choice(['scikit-learn', 'xgboost', 'tensorflow', 'pytorch']),
                    'hyperparameters': {
                        'learning_rate': random.uniform(0.001, 0.1),
                        'max_depth': random.randint(3, 10),
                    }
                }
            )
            
            # Create coefficients for regression models
            if 'Regression' in template['model_type']:
                for idx, feature in enumerate(template['features']):
                    # Stronger coefficients for more important features (first ones)
                    coef_magnitude = random.uniform(0.5, 3.5) if idx < 3 else random.uniform(0.1, 1.5)
                    coef_sign = random.choice([-1, 1])
                    
                    ModelCoefficient.objects.create(
                        engine=engine,
                        feature_name=feature,
                        value=coef_sign * coef_magnitude,
                        p_value=random.uniform(0.0001, 0.05)  # All coefficients are statistically significant
                    )
            
            # Create coefficients for tree-based models (feature importance as coefficients)
            elif 'Forest' in template['model_type'] or 'Boost' in template['model_type']:
                importances = sorted([random.uniform(0, 1) for _ in template['features']], reverse=True)
                total = sum(importances)
                for feature, importance in zip(template['features'], importances):
                    ModelCoefficient.objects.create(
                        engine=engine,
                        feature_name=feature,
                        value=importance / total,  # Normalized importance
                        p_value=None  # Not applicable for tree models
                    )
            
            created_count += 1
            self.stdout.write(f'Created: {name} (R²={r_squared:.4f}, MAPE={mape:.2f}%)')

        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully seeded {created_count} demo models'))
        self.stdout.write(self.style.WARNING('\nNote: These are demo models with dummy binaries for visualization only.'))
        self.stdout.write(self.style.WARNING('They cannot be used for actual predictions.'))
