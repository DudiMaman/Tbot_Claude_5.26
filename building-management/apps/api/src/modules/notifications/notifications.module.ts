import { Module } from '@nestjs/common';
import { NotificationsService } from './notifications.service';
import { ExpoPushSender } from './senders/expo-push.sender';
import { ResendEmailSender } from './senders/resend-email.sender';
import { InforuSmsSender } from './senders/inforu-sms.sender';

@Module({
  providers: [NotificationsService, ExpoPushSender, ResendEmailSender, InforuSmsSender],
  exports: [NotificationsService],
})
export class NotificationsModule {}
