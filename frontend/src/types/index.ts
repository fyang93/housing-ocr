export interface Document {
  id: number;
  filename: string;
  upload_time: string;
  ocr_status: 'pending' | 'processing' | 'done' | 'failed';
  llm_status: 'pending' | 'processing' | 'done' | 'failed';
  ocr_text?: string;
  properties?: PropertyDetails;
  favorite: number;
  extracted_model?: string;
  station_durations?: StationDuration[];
  image_width?: number;
  image_height?: number;
  file_hash?: string;
}

export interface PropertyDetails {
  address?: string;
  price?: number;
  property_name?: string;
  property_type?: string;
  room_layout?: string;
  exclusive_area?: number;
  build_year?: number;
  structure?: string;
  floor_number?: number;
  total_floors?: number;
  orientation?: string;
  corner_room?: boolean;
  management_fee?: number;
  repair_fee?: number;
  balcony_area?: number;
  nearest_station?: string;
  train_line?: string;
  walking_minutes?: number;
  prefecture?: string;
  city?: string;
  land_rights?: string;
  current_status?: string;
  handover_date?: string;
  parking?: string;
  pet_policy?: string;
  stations?: Station[];
}

export interface Station {
  name: string;
  line: string;
  walking_minutes: string;
}

export interface StationDuration {
  id: number;
  location_name: string;
  duration: number;
  show_in_tag: number;
}

export interface Location {
  id: number;
  name: string;
  display_order: number;
  show_in_tag: number;
}

export interface FilterState {
  search: string;
  priceMin: number | null;
  priceMax: number | null;
  areaMin: number | null;
  areaMax: number | null;
  walking: number | null;
  propertyTypes: string[];
  room: string | null;
  pet: boolean;
  favorite: boolean;
}
