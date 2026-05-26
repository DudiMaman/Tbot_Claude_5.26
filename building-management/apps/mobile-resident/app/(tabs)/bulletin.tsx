import { View, Text, ScrollView, StyleSheet } from 'react-native';

export default function BulletinScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.title}>לוח מודעות</Text>
      <View style={styles.card}>
        <View style={styles.pin}><Text style={styles.pinText}>📌 נעוץ</Text></View>
        <Text style={styles.postTitle}>ניקוי גנים — יום שלישי</Text>
        <Text style={styles.postBody}>אנא הזיזו רכבים מהחניות מ-8:00 עד 12:00.</Text>
        <Text style={styles.meta}>פורסם לפני יומיים</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  title: { fontSize: 24, fontWeight: '700', writingDirection: 'rtl', marginBottom: 12 },
  card: { backgroundColor: 'white', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  pin: { alignSelf: 'flex-start', backgroundColor: '#fef3c7', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, marginBottom: 8 },
  pinText: { fontSize: 11, color: '#92400e', writingDirection: 'rtl' },
  postTitle: { fontWeight: '700', fontSize: 16, writingDirection: 'rtl' },
  postBody: { marginTop: 6, color: '#334155', writingDirection: 'rtl' },
  meta: { marginTop: 8, color: '#94a3b8', fontSize: 12, writingDirection: 'rtl' },
});
