from django.urls import path
from . import views

app_name = "adminpanel"

urlpatterns = [
    # --- DASHBOARD ---
    path("", views.dashboard, name="dashboard"),

    # --- CATEGORIES ---
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_add, name="category_add"),
    path("categories/edit/<int:category_id>/", views.category_edit, name="category_edit"),
    path("categories/delete/<int:category_id>/", views.category_delete, name="category_delete"),

    # --- BRANDS ---
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/add/", views.brand_add, name="brand_add"),
    path("brands/edit/<int:brand_id>/", views.brand_edit, name="brand_edit"),
    path("brands/delete/<int:brand_id>/", views.brand_delete, name="brand_delete"),

    # --- PRODUCTS ---
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/edit/<int:product_id>/", views.product_edit, name="product_edit"),
    path("products/delete/<int:product_id>/", views.product_delete, name="product_delete"),

    # --- CONTACT LENSES (Products) ---
    path("contact-lenses/", views.contact_lens_list, name="contact_lens_list"),
    path("contact-lenses/add/", views.contact_lens_add, name="contact_lens_add"),
    path("contact-lenses/edit/<int:lens_id>/", views.contact_lens_edit, name="contact_lens_edit"),
    path("contact-lenses/delete/<int:lens_id>/", views.contact_lens_delete, name="contact_lens_delete"),

    # --- CONTACT LENS COLORS ---
    path("contact-lenses/<int:lens_id>/colors/", views.contact_lens_color_list, name="contact_lens_color_list"),
    path("contact-lenses/<int:lens_id>/colors/add/", views.contact_lens_color_add, name="contact_lens_color_add"),
    path("contact-lenses/colors/edit/<int:color_id>/", views.contact_lens_color_edit, name="contact_lens_color_edit"),
    path("contact-lenses/colors/delete/<int:color_id>/", views.contact_lens_color_delete, name="contact_lens_color_delete"),

    # --- LENS CATEGORIES ---
    path("lens-categories/", views.lens_category_list, name="lens_category_list"),
    path("lens-categories/add/", views.lens_category_add, name="lens_category_add"),
    path("lens-categories/edit/<int:cat_id>/", views.lens_category_edit, name="lens_category_edit"),
    path("lens-categories/delete/<int:cat_id>/", views.lens_category_delete, name="lens_category_delete"),

    # --- LENS OPTIONS ---
    path("lens-options/", views.lens_option_list, name="lens_option_list"),
    path("lens-options/add/", views.lens_option_add, name="lens_option_add"),
    path("lens-options/edit/<int:option_id>/", views.lens_option_edit, name="lens_option_edit"),
    path("lens-options/delete/<int:option_id>/", views.lens_option_delete, name="lens_option_delete"),

    # --- LENS ADD-ONS ---
    path("lens-addons/", views.lens_addon_list, name="lens_addon_list"),
    path("lens-addons/add/", views.lens_addon_add, name="lens_addon_add"),
    path("lens-addons/edit/<int:addon_id>/", views.lens_addon_edit, name="lens_addon_edit"),
    path("lens-addons/delete/<int:addon_id>/", views.lens_addon_delete, name="lens_addon_delete"),

    # --- LENS OPTION ADD-ON MANAGEMENT ---
    path("lens-options/<int:option_id>/addons/", views.lens_option_addon_manage, name="lens_option_addon_manage"),

    # --- SUNGLASS LENSES ---
    path("sunglass-lenses/", views.sunglass_lens_list, name="sunglass_lens_list"),
    path("sunglass-lenses/add/", views.sunglass_lens_add, name="sunglass_lens_add"),
    path("sunglass-lenses/edit/<int:option_id>/", views.sunglass_lens_edit, name="sunglass_lens_edit"),
    path("sunglass-lenses/delete/<int:option_id>/", views.sunglass_lens_delete, name="sunglass_lens_delete"),

    # --- ORDERS ---
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/update-status/", views.order_update_status, name="order_update_status"),
    path("orders/<int:order_id>/update-payment/", views.order_update_payment_status, name="order_update_payment_status"),

    # --- EYE TEST BOOKINGS ---
    path("eye-tests/", views.eye_test_list, name="eye_test_list"),
    path("eye-tests/<int:booking_id>/", views.eye_test_detail, name="eye_test_detail"),
    path("eye-tests/delete/<int:booking_id>/", views.eye_test_delete, name="eye_test_delete"),

    # --- REVIEWS ---
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/approve/<int:review_id>/", views.review_approve, name="review_approve"),
    path("reviews/reject/<int:review_id>/", views.review_reject, name="review_reject"),
    path("reviews/delete/<int:review_id>/", views.review_delete, name="review_delete"),

    # --- USERS ---
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),

    # --- PRODUCT TAGS ---
    path("tags/", views.tag_list, name="tag_list"),
    path("tags/add/", views.tag_add, name="tag_add"),
    path("tags/edit/<int:tag_id>/", views.tag_edit, name="tag_edit"),
    path("tags/delete/<int:tag_id>/", views.tag_delete, name="tag_delete"),

    # --- STORE LOCATIONS ---
    path('stores/', views.store_list, name='store_list'),
    path('stores/add/', views.store_add, name='store_add'),
    path('stores/<int:store_id>/edit/', views.store_edit, name='store_edit'),
    path('stores/<int:store_id>/delete/', views.store_delete, name='store_delete'),

    # --- LIVE CHAT ---
 
    path('chat/', views.chat_list, name='chat_list'),
    path('chat/agent-status/', views.chat_agent_status, name='chat_agent_status'),  # ← specific first
    path('chat/<str:conversation_id>/', views.chat_conversation, name='chat_conversation'),  # ← catch-all last
]