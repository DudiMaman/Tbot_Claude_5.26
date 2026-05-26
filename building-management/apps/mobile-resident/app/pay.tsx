import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { WebView } from 'react-native-webview';
import { useLocalSearchParams } from 'expo-router';

export default function PayScreen() {
  const { charge_id } = useLocalSearchParams<{ charge_id?: string }>();
  const tranzilaIframeUrl = `https://direct.tranzila.com/<supplier>/iframenew.php?currency=1&sum=350&txnref=${charge_id ?? 'demo'}`;

  return (
    <View style={{ flex: 1 }}>
      <Text style={styles.title}>תשלום מאובטח</Text>
      <WebView
        source={{ uri: tranzilaIframeUrl }}
        startInLoadingState
        renderLoading={() => <ActivityIndicator style={{ flex: 1 }} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 18, fontWeight: '700', padding: 16, writingDirection: 'rtl' },
});
