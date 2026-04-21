from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.apps import apps
import pandas as pd
from pathlib import Path
from .models import Cart


def populate_dog_breeds():
    """Tạo danh sách giống chó từ labels.csv"""
    try:
        DogBreed = apps.get_model('classifier', 'DogBreed')
        
        # Đọc danh sách giống từ labels.csv
        csv_path = Path(__file__).parent.parent / "labels.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            breeds = df['breed'].unique()
            
            # Tạo từng giống chó
            for breed_name in breeds:
                # Format tên: dog_breed_name -> Dog Breed Name
                display_name = breed_name.replace('_', ' ').title()
                
                DogBreed.objects.get_or_create(
                    name=display_name,
                    defaults={
                        "description": f"{display_name} - một giống chó xinh đẹp",
                        "characteristics": f"Thông tin về giống {display_name}",
                        "origin": "Chưa cập nhật",
                    }
                )
    except Exception as e:
        print(f"Lỗi khi tạo giống chó: {e}")


# Gọi populate_dog_breeds() sau khi migrate hoàn tất, không phải khi app khởi động
@receiver(post_migrate)
def populate_after_migrate(sender, **kwargs):
    """Populate dog breeds sau migration"""
    if sender.name == 'classifier':
        populate_dog_breeds()


@receiver(post_save, sender=User)
def create_user_cart(sender, instance, created, **kwargs):
    """Tạo giỏ hàng cho người dùng mới"""
    if created:
        Cart.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_cart(sender, instance, **kwargs):
    """Lưu giỏ hàng khi lưu người dùng"""
    try:
        instance.cart.save()
    except Cart.DoesNotExist:
        Cart.objects.create(user=instance)
