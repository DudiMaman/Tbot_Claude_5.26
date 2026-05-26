import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function TicketsScreen() {
  const router = useRouter();
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <View style={styles.header}>
        <Text style={styles.title}>פניות שירות</Text>
        <TouchableOpacity style={styles.button} onPress={() => router.push('/ticket-new')}>
          <Ionicons name="add" size={20} color="white" />
          <Text style={styles.buttonText}>פנייה חדשה</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.empty}>אין פניות פתוחות</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 24, fontWeight: '700', writingDirection: 'rtl' },
  button: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#4f46e5', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  buttonText: { color: 'white', fontWeight: '600', writingDirection: 'rtl' },
  empty: { textAlign: 'center', color: '#64748b', marginTop: 40, writingDirection: 'rtl' },
});
