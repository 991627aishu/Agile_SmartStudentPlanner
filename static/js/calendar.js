// Custom Date Picker
class CalendarPicker {
    constructor(inputElement) {
        this.input = inputElement;
        this.selectedDate = null;
        this.currentMonth = new Date();
        this.createCalendarPopup();
        this.attachEvents();
    }

    createCalendarPopup() {
        this.popup = document.createElement('div');
        this.popup.className = 'calendar-popup';
        this.popup.style.cssText = `
            position: absolute;
            background: #1a1a2e;
            border: 1px solid #2a2a3e;
            border-radius: 12px;
            padding: 16px;
            z-index: 10000;
            display: none;
            width: 280px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        `;
        document.body.appendChild(this.popup);
    }

    attachEvents() {
        this.input.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.showPopup();
        });

        document.addEventListener('click', (e) => {
            if (!this.popup.contains(e.target) && e.target !== this.input) {
                this.popup.style.display = 'none';
            }
        });
    }

    showPopup() {
        this.renderCalendar();
        const rect = this.input.getBoundingClientRect();
        this.popup.style.top = rect.bottom + window.scrollY + 5 + 'px';
        this.popup.style.left = rect.left + window.scrollX + 'px';
        this.popup.style.display = 'block';
    }

    renderCalendar() {
        const year = this.currentMonth.getFullYear();
        const month = this.currentMonth.getMonth();
        
        const firstDay = new Date(year, month, 1);
        const startDay = firstDay.getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        let html = `
            <div style="text-align: center; margin-bottom: 12px;">
                <button class="calendar-prev" style="background: #2a2a3e; border: none; color: white; cursor: pointer; padding: 5px 10px; border-radius: 6px;">◀</button>
                <span style="margin: 0 15px; font-weight: bold;">${this.getMonthName(month)} ${year}</span>
                <button class="calendar-next" style="background: #2a2a3e; border: none; color: white; cursor: pointer; padding: 5px 10px; border-radius: 6px;">▶</button>
            </div>
            <div style="display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 10px;">
                <div style="color: #ff4d6d;">S</div>
                <div>M</div><div>T</div><div>W</div><div>T</div><div>F</div>
                <div style="color: #ff4d6d;">S</div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px;">
        `;
        
        for (let i = 0; i < startDay; i++) {
            html += `<div></div>`;
        }
        
        for (let day = 1; day <= daysInMonth; day++) {
            const cellDate = new Date(year, month, day);
            const isToday = cellDate.toDateString() === today.toDateString();
            const isSelected = this.selectedDate && cellDate.toDateString() === this.selectedDate.toDateString();
            
            let bgColor = '';
            let textColor = 'white';
            if (isToday) {
                bgColor = '#6c63ff';
            }
            if (isSelected) {
                bgColor = '#00d4aa';
            }
            
            html += `
                <div class="calendar-day" 
                     data-year="${year}" 
                     data-month="${month}" 
                     data-day="${day}"
                     style="
                        text-align: center;
                        padding: 6px;
                        cursor: pointer;
                        border-radius: 8px;
                        background: ${bgColor};
                        color: ${textColor};
                     ">
                    ${day}
                </div>
            `;
        }
        
        html += `</div>`;
        
        html += `
            <div style="text-align: center; margin-top: 12px; padding-top: 10px; border-top: 1px solid #2a2a3e;">
                <button class="calendar-today-btn" style="background: #6c63ff; color: white; border: none; padding: 6px 15px; border-radius: 6px; cursor: pointer;">Today</button>
            </div>
        `;
        
        this.popup.innerHTML = html;
        
        this.popup.querySelector('.calendar-prev')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentMonth.setMonth(this.currentMonth.getMonth() - 1);
            this.renderCalendar();
        });
        
        this.popup.querySelector('.calendar-next')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.currentMonth.setMonth(this.currentMonth.getMonth() + 1);
            this.renderCalendar();
        });
        
        this.popup.querySelectorAll('.calendar-day').forEach(day => {
            day.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const year = parseInt(day.dataset.year);
                const month = parseInt(day.dataset.month);
                const dayNum = parseInt(day.dataset.day);
                this.selectedDate = new Date(year, month, dayNum);
                const formattedDate = `${year}-${String(month + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
                this.input.value = formattedDate;
                this.popup.style.display = 'none';
                
                const event = new Event('change', { bubbles: true });
                this.input.dispatchEvent(event);
            });
        });
        
        this.popup.querySelector('.calendar-today-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const today = new Date();
            const formattedDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
            this.input.value = formattedDate;
            this.popup.style.display = 'none';
        });
    }
    
    getMonthName(month) {
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
        return months[month];
    }
}

// Initialize calendar pickers
document.addEventListener('DOMContentLoaded', () => {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        input.type = 'text';
        input.placeholder = 'Click to select date';
        input.readOnly = true;
        new CalendarPicker(input);
    });
});