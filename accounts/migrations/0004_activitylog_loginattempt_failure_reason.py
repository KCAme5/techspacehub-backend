# Generated manually to resolve missing table error in production

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='loginattempt',
            name='failure_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('login_success', 'Login Success'), ('login_failed', 'Login Failed'), ('logout', 'Logout'), ('register', 'Registration'), ('password_change', 'Password Change'), ('password_reset', 'Password Reset'), ('oauth_login', 'OAuth Login'), ('user_created', 'User Created'), ('user_updated', 'User Updated'), ('user_deleted', 'User Deleted'), ('user_verified', 'User Verified'), ('user_suspended', 'User Suspended'), ('course_created', 'Course Created'), ('course_updated', 'Course Updated'), ('course_deleted', 'Course Deleted'), ('course_published', 'Course Published'), ('enrollment_created', 'Enrollment Created'), ('payment_success', 'Payment Success'), ('payment_failed', 'Payment Failed'), ('withdrawal_requested', 'Withdrawal Requested'), ('withdrawal_approved', 'Withdrawal Approved'), ('withdrawal_rejected', 'Withdrawal Rejected'), ('refund_processed', 'Refund Processed'), ('content_created', 'Content Created'), ('content_updated', 'Content Updated'), ('content_deleted', 'Content Deleted'), ('quiz_submitted', 'Quiz Submitted'), ('project_submitted', 'Project Submitted'), ('suspicious_activity', 'Suspicious Activity'), ('rate_limit_exceeded', 'Rate Limit Exceeded'), ('unauthorized_access', 'Unauthorized Access Attempt'), ('other', 'Other')], max_length=50)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('severity', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical')], default='info', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['-timestamp'], name='accounts_ac_timesta_04c55a_idx'),
                    models.Index(fields=['action'], name='accounts_ac_action_28f244_idx'),
                    models.Index(fields=['severity'], name='accounts_ac_severit_323212_idx'),
                    models.Index(fields=['user', '-timestamp'], name='accounts_ac_user_id_4719b6_idx'),
                ],
            },
        ),
    ]
