import { Stack } from 'expo-router';
import { I18nManager } from 'react-native';

// Force RTL for Hebrew
if (!I18nManager.isRTL) {
  I18nManager.allowRTL(true);
  I18nManager.forceRTL(true);
}

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="claim" />
      <Stack.Screen name="pay" />
      <Stack.Screen name="ticket-new" options={{ presentation: 'modal' }} />
    </Stack>
  );
}
