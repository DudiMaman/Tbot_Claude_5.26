import { Redirect } from 'expo-router';
// In a real app: check auth state and redirect accordingly.
export default function Index() {
  return <Redirect href="/(tabs)/home" />;
}
