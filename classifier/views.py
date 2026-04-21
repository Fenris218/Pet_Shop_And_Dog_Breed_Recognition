from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from decimal import Decimal

from django.db import close_old_connections
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from .forms import ImageUploadForm
from .models import (
    UploadedImage, PredictionJob, Dog, DogBreed, Cart, CartItem, 
    Order, OrderItem
)
import numpy as np

import tensorflow as tf
import cv2


_MODEL_LOCK = threading.Lock()
_MODEL = None
_BREED_MODEL = None
_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_CLASS_NAMES = ["Cat", "Dog"]  # Cho phân loại mèo/chó

# 120 giống chó từ labels.csv (theo thứ tự alphabet)
_DOG_BREED_NAMES = [
    "affenpinscher", "afghan_hound", "african_hunting_dog", "airedale",
    "american_staffordshire_terrier", "appenzeller", "australian_terrier",
    "basenji", "basset", "beagle", "bedlington_terrier", "bernese_mountain_dog",
    "black-and-tan_coonhound", "blenheim_spaniel", "bloodhound", "bluetick",
    "border_collie", "border_terrier", "borzoi", "boston_bull",
    "bouvier_des_flandres", "boxer", "brabancon_griffon", "briard",
    "brittany_spaniel", "bull_mastiff", "cairn", "cardigan",
    "chesapeake_bay_retriever", "chihuahua", "chow", "clumber",
    "cocker_spaniel", "collie", "curly-coated_retriever", "dandie_dinmont",
    "dhole", "dingo", "doberman", "english_foxhound",
    "english_setter", "english_springer", "entlebucher", "eskimo_dog",
    "flat-coated_retriever", "french_bulldog", "german_shepherd",
    "german_short-haired_pointer", "giant_schnauzer", "golden_retriever",
    "gordon_setter", "great_dane", "great_pyrenees", "greater_swiss_mountain_dog",
    "groenendael", "ibizan_hound", "irish_setter", "irish_terrier",
    "irish_water_spaniel", "irish_wolfhound", "italian_greyhound",
    "japanese_spaniel", "keeshond", "kelpie", "kerry_blue_terrier",
    "komondor", "kuvasz", "labrador_retriever", "lakeland_terrier",
    "leonberg", "lhasa", "malamute", "malinois", "maltese_dog",
    "mexican_hairless", "miniature_pinscher", "miniature_poodle",
    "miniature_schnauzer", "newfoundland", "norfolk_terrier",
    "norwegian_elkhound", "norwich_terrier", "old_english_sheepdog",
    "otterhound", "papillon", "pekinese", "pembroke", "pomeranian",
    "pug", "redbone", "rhodesian_ridgeback", "rottweiler",
    "saint_bernard", "saluki", "samoyed", "schipperke", "scotch_terrier",
    "scottish_deerhound", "sealyham_terrier", "shetland_sheepdog",
    "shih-tzu", "siberian_husky", "silky_terrier",
    "soft-coated_wheaten_terrier", "staffordshire_bullterrier",
    "standard_poodle", "standard_schnauzer", "sussex_spaniel",
    "tibetan_mastiff", "tibetan_terrier", "toy_poodle", "toy_terrier",
    "vizsla", "walker_hound", "weimaraner", "welsh_springer_spaniel",
    "west_highland_white_terrier", "whippet", "wire-haired_fox_terrier",
    "yorkshire_terrier"
]



def _load_model_once():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL =  tf.keras.models.load_model("cats_dogs_model.keras", compile=False)
    return _MODEL


def _load_breed_model_once():
    """Load mô hình nhận diện giống chó"""
    global _BREED_MODEL
    if _BREED_MODEL is None:
        with _MODEL_LOCK:
            if _BREED_MODEL is None:
                _BREED_MODEL = tf.keras.models.load_model("dog_breed_model.keras", compile=False)
    return _BREED_MODEL



def predict_image(image_path):
    model = _load_model_once()
    img = cv2.imread(image_path)

    if img is None:
        return {
            "label": None,
            "confidence": None,
            "error": "Không đọc được ảnh. Kiểm tra lại đường dẫn.",
        }

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (224, 224))
    img = img.astype("float32") / 255.0   # chuẩn hóa giống lúc train
    img = np.expand_dims(img, axis=0)     # (1, 224, 224, 3)

    prediction = model.predict(img, verbose=0)
    class_id = int(np.argmax(prediction))
    confidence = float(np.max(prediction)) * 100

    return {
        "label": _CLASS_NAMES[class_id],
        "confidence": confidence,
        "error": None,
    }


def predict_breed(image_path):
    """Nhận diện giống chó từ ảnh"""
    model = _load_breed_model_once()
    img = cv2.imread(image_path)

    if img is None:
        return {
            "label": None,
            "confidence": None,
            "error": "Không đọc được ảnh. Kiểm tra lại đường dẫn.",
        }

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (128, 128))  # Model train với 128x128
    img = img.astype("float32") / 255.0   # chuẩn hóa giống lúc train
    img = np.expand_dims(img, axis=0)     # (1, 128, 128, 3)

    prediction = model.predict(img, verbose=0)
    class_id = int(np.argmax(prediction))
    confidence = float(np.max(prediction)) * 100

    # Lấy tên giống từ danh sách và format thành title case
    breed_name = _DOG_BREED_NAMES[class_id]
    breed_display = breed_name.replace('_', ' ').title()

    return {
        "label": breed_display,
        "confidence": confidence,
        "error": None,
    }


def _run_prediction_job(job_id):
    close_old_connections()
    PredictionJob.objects.filter(id=job_id).update(status="running")
    try:
        job = PredictionJob.objects.select_related("user").get(id=job_id)
        result = predict_breed(job.image.path)  # Sử dụng breed model

        PredictionJob.objects.filter(id=job_id).update(
            status="done",
            prediction=result["label"],
            confidence=result["confidence"],
            completed_at=timezone.now(),
        )

        UploadedImage.objects.create(
            user=job.user,
            image=job.image,
            prediction=result["label"],
            confidence=result["confidence"],
        )
    except Exception as exc:
        PredictionJob.objects.filter(id=job_id).update(
            status="failed",
            error_message=str(exc),
            completed_at=timezone.now(),
        )
    finally:
        close_old_connections()


def _cleanup_job_image(job):
    """Xóa file ảnh upload của job để tiết kiệm dung lượng."""
    if not job.image:
        return

    image_name = job.image.name
    storage = job.image.storage

    try:
        if image_name and storage.exists(image_name):
            storage.delete(image_name)
    except Exception:
        # Không chặn luồng hiển thị kết quả nếu việc xóa file gặp lỗi.
        return

    job.image = ""
    job.save(update_fields=["image", "updated_at"])


# ==================== E-COMMERCE VIEWS ====================

def home_view(request):
    # Hiển thị trang chủ với những chú chó nổi bật
    featured_dogs = Dog.objects.filter(is_available=True).order_by('-created_at')[:6]
    dog_count = Dog.objects.filter(is_available=True).count()
    breed_count = DogBreed.objects.count()
    
    context = {
        'featured_dogs': featured_dogs,
        'dog_count': dog_count,
        'breed_count': breed_count,
    }
    return render(request, "index.html", context)


def dogs_list_view(request):
    # Danh sách tất cả chó bán
    dogs = Dog.objects.filter(is_available=True).select_related('breed')
    
    # Lọc theo giống chó
    breed_id = request.GET.get('breed')
    if breed_id:
        dogs = dogs.filter(breed_id=breed_id)
    
    # Lọc theo giá
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        dogs = dogs.filter(price__gte=min_price)
    if max_price:
        dogs = dogs.filter(price__lte=max_price)
    
    # Tìm kiếm
    search = request.GET.get('search')
    if search:
        dogs = dogs.filter(Q(name__icontains=search) | Q(breed__name__icontains=search))
    
    # Sắp xếp
    sort = request.GET.get('sort', '-created_at')
    dogs = dogs.order_by(sort)
    
    breeds = DogBreed.objects.all()
    
    context = {
        'dogs': dogs,
        'breeds': breeds,
        'selected_breed': breed_id,
        'search': search,
        'sort': sort,
    }
    return render(request, "dogs_list.html", context)


def dog_detail_view(request, dog_id):
    # Xem chi tiết một chú chó
    dog = get_object_or_404(Dog, id=dog_id, is_available=True)
    related_dogs = Dog.objects.filter(
        breed=dog.breed, 
        is_available=True
    ).exclude(id=dog_id)[:4]
    
    context = {
        'dog': dog,
        'related_dogs': related_dogs,
    }
    return render(request, "dog_detail.html", context)


# ==================== CART & CHECKOUT ====================

def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def add_to_cart_view(request, dog_id):
    dog = get_object_or_404(Dog, id=dog_id, is_available=True)
    cart = get_or_create_cart(request.user)
    
    # Kiểm tra xem sản phẩm đã có trong giỏ chưa
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        dog=dog,
        defaults={'quantity': 1}
    )
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    if request.GET.get('buy_now'):
        return redirect('checkout')
    return redirect('view_cart')


@login_required
def view_cart_view(request):
    cart = get_or_create_cart(request.user)
    context = {
        'cart': cart,
        'cart_items': cart.items.all().select_related('dog'),
    }
    return render(request, "cart.html", context)


@login_required
def remove_from_cart_view(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    item.delete()
    return redirect('view_cart')


@login_required
def checkout_view(request):
    cart = get_or_create_cart(request.user)
    cart_items = cart.items.all().select_related('dog')
    
    if not cart_items:
        return redirect('view_cart')
    
    if request.method == "POST":
        customer_name = request.POST.get('name')
        customer_email = request.POST.get('email')
        customer_phone = request.POST.get('phone')
        customer_address = request.POST.get('address')
        
        # Tính tổng tiền
        total_price = sum([item.get_total_price() for item in cart_items])
        
        # Tạo order
        order = Order.objects.create(
            user=request.user,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_address=customer_address,
            total_price=total_price,
            status='pending'
        )
        
        # Tạo order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                dog=item.dog,
                price=item.dog.price,
                quantity=item.quantity
            )
        
        # Xóa giỏ hàng
        cart_items.delete()
        
        return redirect('payment', order_id=order.id)
    
    total_price = sum([item.get_total_price() for item in cart_items])
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'user': request.user,
    }
    return render(request, "checkout.html", context)


@login_required
def payment_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == "POST":
        # Mock payment
        card_number = request.POST.get('card_number')
        cvv = request.POST.get('cvv')
        
        # Validate thông tin thẻ
        if card_number and cvv:
            order.status = 'paid'
            order.save()
            
            # Đánh dấu những chó đã bán là không còn bán
            order_items = order.items.all()
            for item in order_items:
                if item.dog:
                    item.dog.is_available = False
                    item.dog.save()
            
            return redirect('order_success', order_id=order.id)
        else:
            return render(request, "payment.html", {
                'order': order,
                'error': 'Thông tin thẻ không hợp lệ'
            })
    
    context = {'order': order}
    return render(request, "payment.html", context)


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all().select_related('dog')
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, "order_success.html", context)


@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    
    context = {
        'orders': orders,
    }
    return render(request, "order_history.html", context)


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all().select_related('dog')
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, "order_detail.html", context)


# ==================== AUTHENTICATION ====================

def login_view(request):
    if request.method == "POST":
        # Trim whitespace
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "").strip()
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("home")
        else:
            return render(request, "login.html", {
                "error": "Sai tài khoản hoặc mật khẩu"
            })
    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def upload_view(request):
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.cleaned_data["image"]
            job = PredictionJob.objects.create(
                user=request.user,
                image=image,
                status="queued",
            )

            _EXECUTOR.submit(_run_prediction_job, job.id)
            return redirect("result", job_id=job.id)
    else:
        form = ImageUploadForm()

    return render(request, "upload.html", {"form": form})


@login_required
def history_view(request):
    histories = (
        UploadedImage.objects
        .filter(user=request.user)
        .order_by("-uploaded_at")
    )

    return render(request, "history.html", {
        "histories": histories
    })



@login_required
def result_view(request, job_id):
    job = get_object_or_404(PredictionJob, id=job_id, user=request.user)
    return render(request, "result.html", {
        "job": job,
    })


@login_required
def job_status_view(request, job_id):
    job = get_object_or_404(PredictionJob, id=job_id, user=request.user)
    return JsonResponse({
        "status": job.status,
        "label": job.prediction,
        "confidence": job.confidence,
        "error": job.error_message,
    })


# ==================== AI BREED DETECTION ====================

@login_required
def detect_breed_view(request):
    """Tải ảnh lên để nhận diện giống chó"""
    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.cleaned_data["image"]
            job = PredictionJob.objects.create(
                user=request.user,
                image=image,
                status="queued",
            )
            _EXECUTOR.submit(_run_prediction_job, job.id)
            return redirect("breed_detection_result", job_id=job.id)
    else:
        form = ImageUploadForm()

    return render(request, "detect_breed.html", {"form": form})


@login_required
def breed_detection_result_view(request, job_id):
    """Hiển thị kết quả nhận diện và những chó cùng giống"""
    job = get_object_or_404(PredictionJob, id=job_id, user=request.user)

    # Sau khi có kết quả, dọn file upload để giảm tài nguyên lưu trữ.
    if job.status in {"done", "failed"} and job.image:
        _cleanup_job_image(job)
    
    # Nếu nhận diện thành công, tìm kiếm giống chó tương ứng
    related_dogs = None
    if job.status == "done" and job.prediction:
        # Tìm các chú chó của giống được nhận diện (chỉ những chó còn bán)
        try:
            breed = DogBreed.objects.get(name__icontains=job.prediction)
            # Chỉ lấy những chó còn bán (is_available=True)
            related_dogs = Dog.objects.filter(breed=breed, is_available=True)[:4]
        except DogBreed.DoesNotExist:
            pass
    
    context = {
        'job': job,
        'related_dogs': related_dogs,
    }
    return render(request, "breed_detection_result.html", context)


def signup_view(request):
    if request.method == "POST":
        # Trim whitespace từ tất cả input
        username = request.POST.get("username", "").strip().lower()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # Validate: nhập đầy đủ thông tin
        if not username or not password or not confirm_password:
            return render(request, "signup.html", {
                "error": "Vui lòng nhập đầy đủ thông tin"
            })

        # Validate: độ dài username (min 3 ký tự)
        if len(username) < 3:
            return render(request, "signup.html", {
                "error": "Tên đăng nhập phải có ít nhất 3 ký tự"
            })

        # Validate: độ dài password (min 6 ký tự)
        if len(password) < 6:
            return render(request, "signup.html", {
                "error": "Mật khẩu phải có ít nhất 6 ký tự"
            })

        # Validate: mật khẩu xác nhận khớp
        if password != confirm_password:
            return render(request, "signup.html", {
                "error": "Mật khẩu xác nhận không khớp"
            })

        # Validate: username chưa tồn tại
        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {
                "error": "Tên đăng nhập đã tồn tại"
            })

        # Validate: email chưa tồn tại (nếu nhập email)
        if email and User.objects.filter(email=email).exists():
            return render(request, "signup.html", {
                "error": "Email đã được đăng ký"
            })

        # Tạo user
        user = User.objects.create_user(
            username=username,
            email=email if email else "",
            password=password
        )

        # Gửi thông báo thành công và redirect đến login
        messages.success(request, "Đăng ký thành công! Vui lòng đăng nhập.")
        return redirect("login")

    return render(request, "signup.html")
