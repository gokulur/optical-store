from django.urls import path
from . import views

app_name = "adminpanel"

urlpatterns = [

    # ── DASHBOARD ──────────────────────────────────────────────────────────────
    path("", views.dashboard, name="dashboard"),

    # ── CATEGORIES ─────────────────────────────────────────────────────────────
    path("categories/",                              views.category_list,   name="category_list"),
    path("categories/add/",                          views.category_add,    name="category_add"),
    path("categories/edit/<int:category_id>/",       views.category_edit,   name="category_edit"),
    path("categories/delete/<int:category_id>/",     views.category_delete, name="category_delete"),

    # ── BRANDS ─────────────────────────────────────────────────────────────────
    path("brands/",                          views.brand_list,   name="brand_list"),
    path("brands/add/",                      views.brand_add,    name="brand_add"),
    path("brands/edit/<int:brand_id>/",      views.brand_edit,   name="brand_edit"),
    path("brands/delete/<int:brand_id>/",    views.brand_delete, name="brand_delete"),

    # ── PRODUCTS ───────────────────────────────────────────────────────────────
    path("products/",                            views.product_list,   name="product_list"),
    path("products/add/",                        views.product_add,    name="product_add"),
    path("products/edit/<int:product_id>/",      views.product_edit,   name="product_edit"),
    path("products/delete/<int:product_id>/",    views.product_delete, name="product_delete"),

    # ── CONTACT LENSES (Products) ──────────────────────────────────────────────
    path("contact-lenses/",                          views.contact_lens_list,   name="contact_lens_list"),
    path("contact-lenses/add/",                      views.contact_lens_add,    name="contact_lens_add"),
    path("contact-lenses/edit/<int:lens_id>/",       views.contact_lens_edit,   name="contact_lens_edit"),
    path("contact-lenses/delete/<int:lens_id>/",     views.contact_lens_delete, name="contact_lens_delete"),

    # ── CONTACT LENS COLORS ────────────────────────────────────────────────────
    path("contact-lenses/<int:lens_id>/colors/",             views.contact_lens_color_list,   name="contact_lens_color_list"),
    path("contact-lenses/<int:lens_id>/colors/add/",         views.contact_lens_color_add,    name="contact_lens_color_add"),
    path("contact-lenses/colors/edit/<int:color_id>/",       views.contact_lens_color_edit,   name="contact_lens_color_edit"),
    path("contact-lenses/colors/delete/<int:color_id>/",     views.contact_lens_color_delete, name="contact_lens_color_delete"),

    # ── PRESCRIPTION LENS CATEGORIES (lenses app) ──────────────────────────────
    path("lens-categories/",                         views.lens_category_list,   name="lens_category_list"),
    path("lens-categories/add/",                     views.lens_category_add,    name="lens_category_add"),
    path("lens-categories/edit/<int:cat_id>/",       views.lens_category_edit,   name="lens_category_edit"),
    path("lens-categories/delete/<int:cat_id>/",     views.lens_category_delete, name="lens_category_delete"),

    # ── PRESCRIPTION LENS OPTIONS (lenses app — cart flow) ─────────────────────
    path("prescription-lenses/",                               views.prescription_lens_option_list,   name="prescription_lens_option_list"),
    path("prescription-lenses/add/",                           views.prescription_lens_option_add,    name="prescription_lens_option_add"),
    path("prescription-lenses/edit/<int:option_id>/",          views.prescription_lens_option_edit,   name="prescription_lens_option_edit"),
    path("prescription-lenses/delete/<int:option_id>/",        views.prescription_lens_option_delete, name="prescription_lens_option_delete"),
    path("prescription-lenses/<int:option_id>/addons/",        views.lens_option_addon_manage,        name="lens_option_addon_manage"),

    # ── LENS ADD-ONS / COATINGS ────────────────────────────────────────────────
    path("lens-addons/",                         views.lens_addon_list,   name="lens_addon_list"),
    path("lens-addons/add/",                     views.lens_addon_add,    name="lens_addon_add"),
    path("lens-addons/edit/<int:addon_id>/",     views.lens_addon_edit,   name="lens_addon_edit"),
    path("lens-addons/delete/<int:addon_id>/",   views.lens_addon_delete, name="lens_addon_delete"),

    # ── SUNGLASS LENS OPTIONS ──────────────────────────────────────────────────
    path("sunglass-lenses/",                             views.sunglass_lens_list,   name="sunglass_lens_list"),
    path("sunglass-lenses/add/",                         views.sunglass_lens_add,    name="sunglass_lens_add"),
    path("sunglass-lenses/edit/<int:option_id>/",        views.sunglass_lens_edit,   name="sunglass_lens_edit"),
    path("sunglass-lenses/delete/<int:option_id>/",      views.sunglass_lens_delete, name="sunglass_lens_delete"),

    # ── MEDICAL LENS BRANDS (catalog app LensBrand) ────────────────────────────
    path("medical/brands/",                          views.lens_brand_list,   name="lens_brand_list"),
    path("medical/brands/add/",                      views.lens_brand_add,    name="lens_brand_add"),
    path("medical/brands/edit/<int:brand_id>/",      views.lens_brand_edit,   name="lens_brand_edit"),
    path("medical/brands/delete/<int:brand_id>/",    views.lens_brand_delete, name="lens_brand_delete"),

    # ── MEDICAL LENS TYPES (per LensBrand) ────────────────────────────────────
    path("medical/brands/<int:brand_id>/types/",             views.lens_type_list,   name="lens_type_list"),
    path("medical/brands/<int:brand_id>/types/add/",         views.lens_type_add,    name="lens_type_add"),
    path("medical/types/edit/<int:type_id>/",                views.lens_type_edit,   name="lens_type_edit"),
    path("medical/types/delete/<int:type_id>/",              views.lens_type_delete, name="lens_type_delete"),

    # ── MEDICAL LENS OPTIONS (catalog app LensOption) ─────────────────────────
    path("medical-lenses/",                              views.medical_lens_list,   name="medical_lens_list"),
    path("medical-lenses/add/",                          views.medical_lens_add,    name="medical_lens_add"),
    path("medical-lenses/edit/<int:option_id>/",         views.medical_lens_edit,   name="medical_lens_edit"),
    path("medical-lenses/delete/<int:option_id>/",       views.medical_lens_delete, name="medical_lens_delete"),

    # ── ORDERS ─────────────────────────────────────────────────────────────────
    path("orders/",                                      views.order_list,                  name="order_list"),
    path("orders/<int:order_id>/",                       views.order_detail,                name="order_detail"),
    path("orders/<int:order_id>/update-status/",         views.order_update_status,         name="order_update_status"),
    path("orders/<int:order_id>/update-payment/",        views.order_update_payment_status, name="order_update_payment_status"),

    # ── EYE TEST BOOKINGS ──────────────────────────────────────────────────────
    path("eye-tests/",                           views.eye_test_list,   name="eye_test_list"),
    path("eye-tests/<int:booking_id>/",          views.eye_test_detail, name="eye_test_detail"),
    path("eye-tests/delete/<int:booking_id>/",   views.eye_test_delete, name="eye_test_delete"),

    # ── REVIEWS ────────────────────────────────────────────────────────────────
    path("reviews/",                             views.review_list,    name="review_list"),
    path("reviews/approve/<int:review_id>/",     views.review_approve, name="review_approve"),
    path("reviews/reject/<int:review_id>/",      views.review_reject,  name="review_reject"),
    path("reviews/delete/<int:review_id>/",      views.review_delete,  name="review_delete"),

    # ── USERS ──────────────────────────────────────────────────────────────────
    path("users/",                                   views.user_list,          name="user_list"),
    path("users/<int:user_id>/",                     views.user_detail,        name="user_detail"),
    path("users/<int:user_id>/toggle-active/",       views.user_toggle_active, name="user_toggle_active"),

    # ── PRODUCT TAGS ───────────────────────────────────────────────────────────
    path("tags/",                        views.tag_list,   name="tag_list"),
    path("tags/add/",                    views.tag_add,    name="tag_add"),
    path("tags/edit/<int:tag_id>/",      views.tag_edit,   name="tag_edit"),
    path("tags/delete/<int:tag_id>/",    views.tag_delete, name="tag_delete"),

    # ── STORE LOCATIONS ────────────────────────────────────────────────────────
    path("stores/",                              views.store_list,   name="store_list"),
    path("stores/add/",                          views.store_add,    name="store_add"),
    path("stores/<int:store_id>/edit/",          views.store_edit,   name="store_edit"),
    path("stores/<int:store_id>/delete/",        views.store_delete, name="store_delete"),

    # ── LIVE CHAT ──────────────────────────────────────────────────────────────
    path("chat/",                            views.chat_list,         name="chat_list"),
    path("chat/agent-status/",               views.chat_agent_status, name="chat_agent_status"),
    path("chat/<str:conversation_id>/",      views.chat_conversation, name="chat_conversation"),

    # ── BANNERS ────────────────────────────────────────────────────────────────
    path("banners/",                             views.banner_list,          name="banner_list"),
    path("banners/add/",                         views.banner_add,           name="banner_add"),
    path("banners/<int:banner_id>/edit/",        views.banner_edit,          name="banner_edit"),
    path("banners/<int:banner_id>/delete/",      views.banner_delete,        name="banner_delete"),
    path("banners/<int:banner_id>/toggle/",      views.banner_toggle_active, name="banner_toggle_active"),

    # ── PROMOTIONS / COUPONS ───────────────────────────────────────────────────
    path("promotions/",                              views.coupon_list,          name="coupon_list"),
    path("promotions/add/",                          views.coupon_add,           name="coupon_add"),
    path("promotions/<int:coupon_id>/edit/",         views.coupon_edit,          name="coupon_edit"),
    path("promotions/<int:coupon_id>/delete/",       views.coupon_delete,        name="coupon_delete"),
    path("promotions/usage/",                        views.coupon_usage_history, name="coupon_usage_history"),


    path('orders/<int:order_id>/update-tracking/', views.order_update_tracking, name='order_update_tracking'),
    path('orders/<int:order_id>/update-notes/',    views.order_update_notes,    name='order_update_notes'),


    path('jobs/',                       views.job_list,           name='job_list'),
    path('jobs/add/',                   views.job_add,            name='job_add'),
    path('jobs/<int:job_id>/',          views.job_detail,         name='job_detail'),
    path('jobs/<int:job_id>/edit/',     views.job_edit,           name='job_edit'),
    path('jobs/<int:job_id>/status/',   views.job_update_status,  name='job_update_status'),
    # path('jobs/<int:job_id>/document/', views.job_upload_documentcument,name='job_upload_document'),
    # path('jobs/<int:job_id>/delete/',   views.job_deletedelete,         name='job_delete'),
    path('jobs/customer-search/',       views.job_customer_search,name='job_customer_search'),
]


