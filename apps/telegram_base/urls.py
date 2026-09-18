from apps.telegram_base import views as telegram_views

urlpatterns = [
    # ...
    path('api/cron/tick/', telegram_views.cron_tick, name='cron_tick'),
    # ...
]