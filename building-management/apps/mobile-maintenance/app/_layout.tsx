import { Stack } from 'expo-router';
import { I18nManager } from 'react-native';

if (!I18nManager.isRTL) {
  I18nManager.allowRTL(true);
  I18nManager.forceRTL(true);
}

export default function RootLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
