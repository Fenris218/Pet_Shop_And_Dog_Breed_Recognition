print(">>> classifier.urls LOADED <<<")
from django.contrib import admin
from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # ==================== HOME & BROWSING ====================
    path("", views.home_view, name="home"),
    path("dogs/", views.dogs_list_view, name="dogs_list"),
    path("dog/<int:dog_id>/", views.dog_detail_view, name="dog_detail"),
    
    # ==================== SHOPPING CART & CHECKOUT ====================
    path("cart/", views.view_cart_view, name="view_cart"),
    path("add-to-cart/<int:dog_id>/", views.add_to_cart_view, name="add_to_cart"),
    path("remove-from-cart/<int:item_id>/", views.remove_from_cart_view, name="remove_from_cart"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("payment/<int:order_id>/", views.payment_view, name="payment"),
    path("order/success/<int:order_id>/", views.order_success_view, name="order_success"),
    path("orders/", views.order_history_view, name="order_history"),
    path("order/<int:order_id>/", views.order_detail_view, name="order_detail"),
    
    # ==================== AUTHENTICATION ====================
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    
    # ==================== AI BREED DETECTION ====================
    path("detect-breed/", views.detect_breed_view, name="detect_breed"),
    path("breed-detection/<int:job_id>/", views.breed_detection_result_view, name="breed_detection_result"),
    
    # ==================== LEGACY AI DETECTION ====================
    path("upload/", views.upload_view, name="upload"),
    path("result/<int:job_id>/", views.result_view, name="result"),
    path("job-status/<int:job_id>/", views.job_status_view, name="job_status"),
    path("history/", views.history_view, name="history"),
    
    # ==================== CHATBOT API ====================
    path("api/chatbot/message/", api_views.chatbot_message_api, name="chatbot_message"),
    
    # ==================== REST API ====================
    path("api/breeds/", api_views.breeds_list_api, name="api_breeds_list"),
    path("api/breeds/<int:breed_id>/", api_views.breed_detail_api, name="api_breed_detail"),
    path("api/dogs/", api_views.dogs_list_api, name="api_dogs_list"),
    path("api/dogs/<int:dog_id>/", api_views.dog_detail_api, name="api_dog_detail"),
]

