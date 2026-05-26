import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, Alert, Image } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const CATEGORIES = [
  { v: 'plumbing', l: 'אינסטלציה' },
  { v: 'electrical', l: 'חשמל' },
  { v: 'elevator', l: 'מעלית' },
  { v: 'cleaning', l: 'ניקיון' },
  { v: 'common_area', l: 'שטחים משותפים' },
  { v: 'other', l: 'אחר' },
];

export default function NewTicketScreen() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [category, setCategory] = useState('other');
  const [photos, setPhotos] = useState<string[]>([]);

  async function pickImage() {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.7,
    });
    if (!res.canceled && res.assets[0]) {
      setPhotos([...photos, res.assets[0].uri]);
    }
  }

  async function submit() {
    Alert.alert('הפנייה נשלחה', 'נחזור אליכם בהקדם.');
    router.back();
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.title}>פנייה חדשה</Text>

      <Text style={styles.label}>כותרת</Text>
      <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder="תקציר קצר" />

      <Text style={styles.label}>קטגוריה</Text>
      <View style={styles.cats}>
        {CATEGORIES.map((c) => (
          <TouchableOpacity
            key={c.v}
            style={[styles.cat, category === c.v && styles.catActive]}
            onPress={() => setCategory(c.v)}
          >
            <Text style={[styles.catText, category === c.v && styles.catTextActive]}>{c.l}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>תיאור</Text>
      <TextInput
        style={[styles.input, { minHeight: 100, textAlignVertical: 'top' }]}
        value={desc}
        onChangeText={setDesc}
        multiline
        placeholder="פרטו את הבעיה"
      />

      <Text style={styles.label}>תמונות</Text>
      <View style={styles.photos}>
        {photos.map((uri) => (
          <Image key={uri} source={{ uri }} style={styles.photo} />
        ))}
        <TouchableOpacity style={styles.photoAdd} onPress={pickImage}>
          <Ionicons name="camera" size={28} color="#94a3b8" />
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.submit} onPress={submit}>
        <Text style={styles.submitText}>שליחת פנייה</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'white' },
  title: { fontSize: 24, fontWeight: '700', writingDirection: 'rtl' },
  label: { fontSize: 14, color: '#475569', marginTop: 16, writingDirection: 'rtl' },
  input: { borderWidth: 1, borderColor: '#cbd5e1', borderRadius: 10, padding: 12, marginTop: 6, textAlign: 'right', writingDirection: 'rtl' },
  cats: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  cat: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: '#cbd5e1' },
  catActive: { borderColor: '#4f46e5', backgroundColor: '#eef2ff' },
  catText: { color: '#475569', fontSize: 13, writingDirection: 'rtl' },
  catTextActive: { color: '#4f46e5', fontWeight: '600' },
  photos: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  photo: { width: 80, height: 80, borderRadius: 10 },
  photoAdd: { width: 80, height: 80, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: '#cbd5e1', alignItems: 'center', justifyContent: 'center' },
  submit: { marginTop: 32, backgroundColor: '#4f46e5', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  submitText: { color: 'white', fontSize: 16, fontWeight: '700', writingDirection: 'rtl' },
});
