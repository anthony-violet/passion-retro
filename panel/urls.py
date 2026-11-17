from django.urls import path
from panel.views import dashboard, users, forum, posts, quiz, shop, guestbook, maintenance, games, version, ephemerides, navigation, wall_memories, seasonal

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

    # Navigation (sections de la navbar)
    path('navigation/', navigation.nav_section_list, name='panel_nav_sections'),
    path('navigation/create/', navigation.nav_section_create, name='panel_nav_section_create'),
    path('navigation/<int:section_id>/edit/', navigation.nav_section_edit, name='panel_nav_section_edit'),
    path('navigation/<int:section_id>/toggle/', navigation.nav_section_toggle, name='panel_nav_section_toggle'),
    path('navigation/<int:section_id>/delete/', navigation.nav_section_delete, name='panel_nav_section_delete'),

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
    path('decors/', seasonal.seasonal_list, name='panel_seasonal'),
    path('decors/apercu/', seasonal.seasonal_preview, name='panel_seasonal_preview'),

    # Versions
    path('versions/', version.version_list, name='panel_version'),
    path('versions/create/', version.version_create, name='panel_version_create'),
    path('versions/<int:version_id>/edit/', version.version_edit, name='panel_version_edit'),
    path('versions/<int:version_id>/delete/', version.version_delete, name='panel_version_delete'),

    # Games
    path('games/', games.games_overview, name='panel_games'),
    path('games/category/create/', games.category_create, name='panel_games_category_create'),
    path('games/category/<int:category_id>/edit/', games.category_edit, name='panel_games_category_edit'),
    path('games/category/<int:category_id>/delete/', games.category_delete, name='panel_games_category_delete'),

    # Ephemerides
    path('ephemerides/', ephemerides.ephemeride_list, name='panel_ephemerides'),
    path('ephemerides/create/', ephemerides.ephemeride_create, name='panel_ephemeride_create'),
    path('ephemerides/<int:event_id>/edit/', ephemerides.ephemeride_edit, name='panel_ephemeride_edit'),
    path('ephemerides/<int:event_id>/delete/', ephemerides.ephemeride_delete, name='panel_ephemeride_delete'),
    
    # Contributions
    path('ephemerides/contributions/', ephemerides.contributed_ephemeride_list, name='panel_ephemerides_contributions'),
    path('ephemerides/contributions/<int:contribution_id>/review/', ephemerides.contributed_ephemeride_review, name='panel_ephemeride_contribution_review'),

    # Mur des souvenirs
    path('souvenirs/', wall_memories.memory_list, name='panel_memories'),
    path('souvenirs/<int:memory_id>/', wall_memories.memory_review, name='panel_memory_review'),
    path('souvenirs/<int:memory_id>/delete/', wall_memories.memory_delete, name='panel_memory_delete'),
    path('souvenirs/commentaires/', wall_memories.comment_list, name='panel_memory_comments'),
    path('souvenirs/commentaires/<int:comment_id>/toggle/', wall_memories.comment_toggle, name='panel_memory_comment_toggle'),
    path('souvenirs/commentaires/<int:comment_id>/delete/', wall_memories.comment_delete, name='panel_memory_comment_delete'),
    path('souvenirs/consoles/', wall_memories.console_list, name='panel_memory_consoles'),
    path('souvenirs/consoles/create/', wall_memories.console_create, name='panel_memory_console_create'),
    path('souvenirs/consoles/<int:console_id>/edit/', wall_memories.console_edit, name='panel_memory_console_edit'),
    path('souvenirs/consoles/<int:console_id>/delete/', wall_memories.console_delete, name='panel_memory_console_delete'),
]
