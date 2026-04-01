from django.urls import path
from panel.views import dashboard, users, forum, posts, quiz, shop, guestbook, maintenance, games

urlpatterns = [
    # Dashboard
    path('', dashboard.dashboard, name='panel_dashboard'),

    # Users
    path('users/', users.user_list, name='panel_user_list'),
    path('users/<int:user_id>/edit/', users.user_edit, name='panel_user_edit'),
    path('users/<int:user_id>/toggle/', users.user_toggle_active, name='panel_user_toggle'),
    path('users/<int:user_id>/delete/', users.user_delete, name='panel_user_delete'),

    # Forum
    path('forum/', forum.forum_overview, name='panel_forum'),
    path('forum/category/create/', forum.category_create, name='panel_forum_category_create'),
    path('forum/category/<int:category_id>/edit/', forum.category_edit, name='panel_forum_category_edit'),
    path('forum/category/<int:category_id>/delete/', forum.category_delete, name='panel_forum_category_delete'),
    path('forum/forum/create/', forum.forum_create, name='panel_forum_forum_create'),
    path('forum/forum/<int:forum_id>/edit/', forum.forum_edit, name='panel_forum_forum_edit'),
    path('forum/forum/<int:forum_id>/delete/', forum.forum_delete, name='panel_forum_forum_delete'),
    path('forum/topics/', forum.topic_list, name='panel_forum_topics'),
    path('forum/topics/<int:topic_id>/toggle/', forum.topic_toggle_state, name='panel_forum_topic_toggle'),
    path('forum/posts/', forum.post_list, name='panel_forum_posts'),
    path('forum/posts/<int:post_id>/toggle/', forum.post_toggle_active, name='panel_forum_post_toggle'),
    path('forum/posts/<int:post_id>/delete/', forum.post_delete, name='panel_forum_post_delete'),

    # Posts/Articles
    path('posts/', posts.post_list, name='panel_posts'),
    path('posts/<int:post_id>/approve/', posts.post_approve, name='panel_post_approve'),
    path('posts/<int:post_id>/reject/', posts.post_reject, name='panel_post_reject'),
    path('posts/<int:post_id>/edit/', posts.post_edit, name='panel_post_edit'),
    path('posts/<int:post_id>/delete/', posts.post_delete, name='panel_post_delete'),
    path('posts/categories/', posts.category_list, name='panel_post_categories'),
    path('posts/categories/<int:category_id>/delete/', posts.category_delete, name='panel_post_category_delete'),

    # Quiz
    path('quiz/', quiz.quiz_list, name='panel_quiz'),
    path('quiz/<int:quiz_id>/toggle/', quiz.quiz_toggle, name='panel_quiz_toggle'),
    path('quiz/<int:quiz_id>/delete/', quiz.quiz_delete, name='panel_quiz_delete'),
    path('quiz/<int:quiz_id>/detail/', quiz.quiz_detail, name='panel_quiz_detail'),

    # Shop
    path('shop/', shop.shop_overview, name='panel_shop'),
    path('shop/category/create/', shop.category_create, name='panel_shop_category_create'),
    path('shop/category/<int:category_id>/edit/', shop.category_edit, name='panel_shop_category_edit'),
    path('shop/category/<int:category_id>/delete/', shop.category_delete, name='panel_shop_category_delete'),
    path('shop/item/create/', shop.item_create, name='panel_shop_item_create'),
    path('shop/item/<int:item_id>/edit/', shop.item_edit, name='panel_shop_item_edit'),
    path('shop/item/<int:item_id>/delete/', shop.item_delete, name='panel_shop_item_delete'),

    # Guestbook
    path('guestbook/', guestbook.guestbook_list, name='panel_guestbook'),
    path('guestbook/<int:entry_id>/toggle/', guestbook.entry_toggle, name='panel_guestbook_toggle'),
    path('guestbook/<int:entry_id>/delete/', guestbook.entry_delete, name='panel_guestbook_delete'),

    # Maintenance
    path('maintenance/', maintenance.maintenance_view, name='panel_maintenance'),

    # Games
    path('games/', games.games_overview, name='panel_games'),
    path('games/category/create/', games.category_create, name='panel_games_category_create'),
    path('games/category/<int:category_id>/edit/', games.category_edit, name='panel_games_category_edit'),
    path('games/category/<int:category_id>/delete/', games.category_delete, name='panel_games_category_delete'),
]
